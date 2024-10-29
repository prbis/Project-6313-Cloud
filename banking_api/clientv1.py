# client.py

import requests

BASE_URL = "http://127.0.0.1:5000"
token = None

def register(name, email, password):
    response = requests.post(f"{BASE_URL}/register", json={
        "name": name,
        "email": email,
        "password": password
    })
    return response.json()

def login(email, password):
    global token
    response = requests.post(f"{BASE_URL}/login", json={
        "email": email,
        "password": password
    })
    data = response.json()
    token = data.get('token')
    return data

def make_protected_request(endpoint, data=None, method="POST"):
    global token
    headers = {'Authorization': token}
    url = f"{BASE_URL}/{endpoint}"
    if method == "POST":
        response = requests.post(url, json=data, headers=headers)
    else:
        response = requests.get(url, headers=headers)
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        print("Non-JSON response received:", response.text)
        return {"error": "Failed to retrieve response"}

# Example Usage
if __name__ == "__main__":
    # Register Alice and Bob
    alice = register("Alice", "alice@example.com", "password123")
    print("Alice Registration:", alice)
    bob = register("Bob", "bob@example.com", "password456")
    print("Bob Registration:", bob)
    rafat= register("Rafat", "rafat@example.com", "password999")
    print("Rafat Registration:", rafat)

    # Log in as Alice
    login_data = login("alice@example.com", "password123")
    print("Login:", login_data)

    # Check Alice's balance
    if token:
        balance = make_protected_request("balance", method="GET")
        print("Alice's Balance:", balance)

    # Deposit money for Alice
    if token:
        deposit = make_protected_request("deposit", {"amount": 200})
        print("Deposit:", deposit)
    # Withdraw money for Alice
    if token:
        withdraw = make_protected_request("withdraw", {"amount": 50})
        print("Withdraw:", withdraw)

    # Transfer money from Alice to Bob using email
    if token:
        transfer = make_protected_request("transfer", {
            "to_account_email": "bob@example.com",
            "amount": 50
        })
        print("Transfer:", transfer)

    # View Alice's transaction history
    if token:
        history = make_protected_request("transaction_history", method="GET")
        print("Transaction History:", history)
