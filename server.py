import psycopg2
import socket
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv


load_dotenv()
# Config from environment variables
DATABASE_URL        = os.environ["DATABASE_URL"]
REMOTE_DATABASE_URL = os.environ.get("REMOTE_DATABASE_URL")
PORT                = int(os.environ["PORT"])
 
HOUSE_A_TOPIC = os.environ.get("HOUSE_A_TOPIC", "")
HOUSE_B_TOPIC = os.environ.get("HOUSE_B_TOPIC", "")

# Per-DB table names — partner uses different naming convention
LOCAL_VIRTUAL_TABLE  = 'public."table1_virtual"'
REMOTE_VIRTUAL_TABLE = 'public."Table 1_virtual"'
 
PST = timezone(timedelta(hours=-8))
SHARING_START_MS = int(datetime.strptime(
    os.environ.get("SHARING_START", "2026-04-28 00:00:00"),
    "%Y-%m-%d %H:%M:%S"
).replace(tzinfo=PST).timestamp() * 1000)
 

# Conversion factors
LITERS_TO_GALLONS = 0.264172

# Device definitions: how to identify each device type and the relevant sensor keys for each.
DEVICE_TYPES = {
    "fridge": {
        "board_keywords": ["fridge"],
        "moisture_keys": [
            "Moisture Meter - Smart Fridge Moisture Meter",   # House A canonical
            "Moisture Meter - Moist1",                         # House B canonical
        ],
    },
    "dishwasher": {
        "board_keywords": ["dishwasher"],
        "water_keys": [
            "Water consumption sensor",   # House A
            "Water Consumption Sensor",   # House B (case folded by SQL)
        ],
    },
    # Electricity = sum of any ammeter reading on every device, per house.
    "electricity": {
        "board_keywords": ["fridge", "dishwasher"],
        "ammeter_keys": [
            "Ammeter",
            "Ammetor",                   # the typo on House A fridge
            "Ammeter dishwasher",
        ],
    },
}


# Connect to the databases
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("Connected to the database.")
except Exception as e:
    print("Failed to connect to the database: " + str(e))
    exit()

remote_conn = None
remote_cursor = None
if REMOTE_DATABASE_URL:
    try:
        remote_conn = psycopg2.connect(REMOTE_DATABASE_URL)
        remote_cursor = remote_conn.cursor()
        print("Connected to remote DB.")    
    except Exception as e:
        print("Remote DB unavailable: " + str(e))







# Data Aggregation Logic

def or_clause(field_extract, values):
    """Build SQL like: ((field) ILIKE '%v1%' OR (field) ILIKE '%v2%')"""
    if not values:
        return "FALSE"
    return "(" + " OR ".join(f"({field_extract}) ILIKE '%{v}%'" for v in values) + ")"
 
def sum_keys_clause(payload_keys):
    """SUM across all candidate payload keys per row (typically only one is non-null)."""
    parts = [f"COALESCE((payload->>'{k}')::numeric, 0)" for k in payload_keys]
    return " + ".join(parts) if parts else "0"
 
def has_any_key_clause(payload_keys):
    """TRUE if a row has at least one non-null candidate key."""
    parts = [f"(payload->>'{k}') IS NOT NULL" for k in payload_keys]
    return "(" + " OR ".join(parts) + ")" if parts else "FALSE"

# SUM + COUNT for one sensor on one device type for one house in a time window. 
# we rely on the fact that for each device type, the relevant sensor keys are mutually exclusive across the two houses (e.g. "Moisture Meter - Smart Fridge Moisture Meter" only appears in House A, while "Moisture Meter - Moist1" only appears in House B). This allows us to write a single SQL query per house that sums across all candidate keys for that device type, without double-counting any readings.
def aggregate(curs, table_name, board_keywords, payload_keys,
              house_topic, t_start, t_end):
    if curs is None:
        return 0.0, 0
    sql = f"""
        SELECT SUM({sum_keys_clause(payload_keys)}) AS total,
               COUNT(*) AS n
        FROM {table_name}
        WHERE LOWER(payload->>'topic') LIKE '%{house_topic.lower()}%'
          AND {or_clause("payload->>'board_name'", board_keywords)}
          AND (payload->>'timestamp')::bigint * 1000 BETWEEN {t_start} AND {t_end}
          AND {has_any_key_clause(payload_keys)}
    """
    try:
        curs.execute(sql)
        row = curs.fetchone()
        total = float(row[0]) if row and row[0] is not None else 0.0
        n     = int(row[1])   if row else 0
        return total, n
    except Exception as e:
        print("query error:", e)
        try: curs.connection.rollback()
        except Exception: pass
        return 0.0, 0

 
# Local-only for House A. For House B, split window at SHARING_START_MS if needed.
def get_house(board_keywords, payload_keys, house_topic,
              is_partner, t_start, t_end):
    if not is_partner or t_start >= SHARING_START_MS:
        total, n = aggregate(cursor, LOCAL_VIRTUAL_TABLE,
                             board_keywords, payload_keys,
                             house_topic, t_start, t_end)
        return total, n, "fully covered by local DB"
 
    pre_t,  pre_n  = aggregate(remote_cursor, REMOTE_VIRTUAL_TABLE,
                               board_keywords, payload_keys, house_topic,
                               t_start, SHARING_START_MS - 1)
    post_t, post_n = aggregate(cursor, LOCAL_VIRTUAL_TABLE,
                               board_keywords, payload_keys, house_topic,
                               SHARING_START_MS, t_end)
    return pre_t + post_t, pre_n + post_n, "merged remote (pre-sharing) + local (post-sharing)"
 
 
# Run aggregate for both houses over the past `hours`, format the section.
def run_window(board_keywords, payload_keys, hours, unit_label, convert):
    t_end   = now_ms()
    t_start = t_end - hours * 3600 * 1000
 
    a_t, a_n, a_note = get_house(board_keywords, payload_keys, HOUSE_A_TOPIC,
                                 is_partner=False, t_start=t_start, t_end=t_end)
    b_t, b_n, b_note = get_house(board_keywords, payload_keys, HOUSE_B_TOPIC,
                                 is_partner=True,  t_start=t_start, t_end=t_end)
 
    total_n = a_n + b_n
    a_avg = convert(a_t / a_n) if a_n else 0
    b_avg = convert(b_t / b_n) if b_n else 0
    combined = convert((a_t + b_t) / total_n) if total_n else 0
 
    return (
        f"  Window: {to_pst(t_start)} -> {to_pst(t_end)}\n"
        f"    House A:  {a_avg:.2f} {unit_label} ({a_n} readings) [{a_note}]\n"
        f"    House B:  {b_avg:.2f} {unit_label} ({b_n} readings) [{b_note}]\n"
        f"    Combined: {combined:.2f} {unit_label} ({total_n} readings)"
    )




# Query Handler

# Q1: Average kitchen-fridge moisture - past 3 hours / week / month.
def query_fridge_moisture():
    fridge = DEVICE_TYPES["fridge"] 
    no_convert    = lambda x: x
 
    sections = [
        "Average fridge moisture",
        "",
        "[Past 3 hours]",
        run_window(fridge["board_keywords"], fridge["moisture_keys"], 3,     "%RH", no_convert),
        "",
        "[Past week]",
        run_window(fridge["board_keywords"], fridge["moisture_keys"], 24*7,  "%RH", no_convert),
        "",
        "[Past month]",
        run_window(fridge["board_keywords"], fridge["moisture_keys"], 24*30, "%RH", no_convert),
    ]
    return "\n".join(sections)
 


# Utility functions
def now_ms():
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)
 
def to_pst(ms):
    return datetime.fromtimestamp(ms / 1000, tz=PST).strftime("%Y-%m-%d %H:%M:%S PST")




# Set up TCP server
myTCPSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
myTCPSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
myTCPSocket.bind(('0.0.0.0', PORT))
myTCPSocket.listen(5)
print("Server is ready to receive on port " + str(PORT))


incomingSOCKET, incomingAddress = myTCPSocket.accept()
print("Connection from: " + str(incomingAddress))


while True:
    try:

        myData = incomingSOCKET.recv(PORT).decode("utf-8")


        if not myData:
            print("Client has cleanly disconnected.")
            break

        print("Client selected option: " + myData)
        responseMessage = "" 

        # Fridge Moisture
        if myData == "1":

         
            responseMessage = query_fridge_moisture()

        # Dishwasher Water 
        elif myData == "2":

            cursor.execute('SELECT * FROM "Table 1_virtual" LIMIT 5')
            rows = cursor.fetchall()
            responseMessage = "Dishwasher Water Data: " + str(rows)

        # House Electricity 
        elif myData == "3":

            cursor.execute('SELECT * FROM "Table 1_virtual" LIMIT 5')
            rows = cursor.fetchall()
            responseMessage = "Electricity Consumption Data: " + str(rows)


        else:
            responseMessage = "Error: Invalid option received by the server."

        # send results to client
        incomingSOCKET.sendall(responseMessage.encode("utf-8"))

    
    except BrokenPipeError:
        print("The client disconnected abruptly.")
        break
    except Exception as e:
        print("An error occurred: " + str(e))
        break


print("Closing connections...")
incomingSOCKET.close()
cursor.close()
conn.close()