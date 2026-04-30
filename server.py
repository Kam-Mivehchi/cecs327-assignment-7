import psycopg2
import socket
import os 
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]



try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    print("Connected to the database.")
except Exception as e:
    print("Failed to connect to the database: " + str(e))
    exit()


myTCPSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
myTCPSocket.bind(('0.0.0.0', 1024))
myTCPSocket.listen(5)
print("Server is ready to receive on port " + str(1024))


incomingSOCKET, incomingAddress = myTCPSocket.accept()
print("Connection from: " + str(incomingAddress))


while True:
    try:

        myData = incomingSOCKET.recv(1024).decode("utf-8")


        if not myData:
            print("Client has cleanly disconnected.")
            break

        print("Client selected option: " + myData)
        responseMessage = "" 

        # Fridge Moisture
        if myData == "1":

            cursor.execute('SELECT * FROM "Table 1_virtual" LIMIT 5')
            rows = cursor.fetchall()
            responseMessage = "Fridge Moisture Data: " + str(rows)

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