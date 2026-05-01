### Members: Kamyar and Angel 


## Contents
**client.py**: The TCP client script, provides a terminal UI for user to only select one of 3 queries:
1. **What is the average moisture inside our kitchen fridges in the past hours, week
and month?**
2. **What is the average water consumption per cycle across our smart
dishwashers in the past hour, week and month?**
3. **Which house consumed more electricity in the past 24 hours, and by how
much?**

**server.py**: The TCP server script that handles incoming client requests, manages database connections, executes distributed SQL queries, and formats the aggregated results.

**Note:** Used Ubuntu VMs

## Questions:
* **Explain how the system connects to and retrieves data from the relevant sources:**
    * We connect the client vm to server vm via public IP address.
    * We connect the server to our databases using our database urls. Kam's being the local and Angel's being the remote. 
    * The server uses functions to query the 2 dbs for data, data is sent back, the math is done, formatted, and served back to client.
    


* **How distributed query processing was implemented:**
     * House A (Kam's) is the local and House B (Angel's) is the remote house. We're checking when the data sharing between the 2 dbs started. 
        * If the query is for House A then retrieve entirely from the local data from the local db.
        * If the query is for House B then check the retrieval window for the data. We retrieve the data before sharing began from the remote db and then when data reaches the time that sharing began we start to use data from the local db. 
    * Once data is retrieved, the necessary calculations are done, formatted, and then sent back to client.


* **How query completeness was determined:**
    * We determined completeness by making sure all the data is taken into consideration from before data sharing began and from after as well.
* **How DataNiz metadata and data sharing were used:**
    * We use the DataNiz metadata to distinguish between different appliances (IoT devices) within each house. In our SQL queries we filter on the board_name and topic in order to get the sum and count of each device’s sensor data for each house. We also utilize the timestamp data to both filter on specific date ranges and to signal a lookup in the remote database.
    * We used data sharing to fill in gaps that the other db may not possess to make a throrough and complete calculation.

## Instructions to Run

1. **Create a .env file**:
Create a .env file in the same directory as server.py:


```
DATABASE_URL="postgres://user:password@localhost:5432/localdb"
REMOTE_DATABASE_URL="postgres://user:password@remote_ip:5432/remotedb"
PORT=8080
HOUSE_A_TOPIC="example@gmail.com/topic1"
HOUSE_B_TOPIC="example@gmail.com/topic2"
SHARING_START="2026-04-28 00:00:00"
```


2. **Start the Server VM**: 
Run the server script first. Ensure your VM's firewall allows incoming connections on the specified port.


3. **Start the Client VM**:
Run the client script. When prompted, enter the IP address of the Server VM and the configured port number.



