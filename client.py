import socket
# Create a TCP/IP socket
myTCPSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
while True:
        serverIpAddress = (input("Enter the IP address of the server: "))
        serverPortNumber = (input("Enter the port number of the server: "))
        try:
                myTCPSocket.connect((str(serverIpAddress), int(serverPortNumber)))
                print("Successfully connected to the server at " + serverIpAddress + ":" +
                str(serverPortNumber))
                break
        except Exception as e:
                print("Failed to connect to the server: " + str(e))

sessionActive = True
# Send data to the server and receive a response
while sessionActive:

        print("\n--- Smart Home Data Menu ---")
        print("1. What is the average moisture inside our kitchen fridges in the past hours, week and month?")
        print("2. What is the average water consumption per cycle across our smart dishwashers in the past hour, week and month?")
        print("3. Which house consumed more electricity in the past 24 hours, and by how much?")
        userChoice = input("\nEnter the number of your choice (1, 2, or 3): ")
    
    # Validate input and assign the message to send
        if userChoice == "1":
                messageToSend = "1"
        elif userChoice == "2":
                messageToSend = "2"
        elif userChoice == "3":
                messageToSend = "3"
        else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                continue        


        myTCPSocket.sendall(messageToSend.encode("utf-8"))
        serverResponse = myTCPSocket.recv(1024)
        print("server response: " + serverResponse.decode("utf-8"))

# Ask the user if they want to continue the session

        inputFromUser = str(input("Do you want to continue the session? (yes/no): "))
        if inputFromUser.lower() == "no":
                sessionActive = False
        elif inputFromUser.lower() != "yes":
                print("Invalid input. Ending session.")
                sessionActive = False
myTCPSocket.close() 