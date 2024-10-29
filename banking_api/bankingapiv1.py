# banking_api.py

from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
import bcrypt
import jwt
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'E5EEEEEEEEE'  # Replace with a secure key

# MongoDB connection
client = MongoClient("mongodb+srv://ashrafuddinrafat:zspkkdmFMioU3vEa@cluster0.pq8jro5.mongodb.net/banking_system?retryWrites=true&w=majority")

db = client['banking_system']
accounts_collection = db['accounts']
transactions_collection = db['transactions']

# Helper function to retrieve account by ID or email
def get_account(identifier):
    if isinstance(identifier, ObjectId):
        return accounts_collection.find_one({"_id": identifier})
    elif isinstance(identifier, str):
        # Try ObjectId lookup
        try:
            obj_id = ObjectId(identifier)
            account = accounts_collection.find_one({"_id": obj_id})
            if account:
                return account
        except InvalidId:
            pass
        # Fallback to email lookup
        return accounts_collection.find_one({"email": identifier})
    else:
        return None

# JWT decorator to protect routes
def token_required(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing!'}), 403
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = get_account(data['account_id'])
            if not current_user:
                return jsonify({'error': 'User not found!'}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired!'}), 403
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token!'}), 403
        return f(current_user, *args, **kwargs)
    
    wrapper.__name__ = f.__name__  # Avoid Flask conflicts by setting function name
    return wrapper

# Endpoint to register a new account
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    password = data.get("password").encode('utf-8')
    
    if accounts_collection.find_one({"email": email}):
        return jsonify({'error': 'Email already exists!'}), 400

    hashed_password = bcrypt.hashpw(password, bcrypt.gensalt())

    new_account = {
        "name": name,
        "email": email,
        "password": hashed_password,
        "balance": 0,
        "created_at": datetime.utcnow()
    }
    result = accounts_collection.insert_one(new_account)
    account_id = str(result.inserted_id)

    return jsonify({'account_id': account_id, 'message': 'Account registered successfully!'}), 201

# Endpoint to login and get JWT token
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password").encode('utf-8')
    
    user = accounts_collection.find_one({"email": email})
    if not user or not bcrypt.checkpw(password, user['password']):
        return jsonify({'error': 'Invalid credentials!'}), 401

    token = jwt.encode({
        'account_id': str(user['_id']),
        'exp': datetime.utcnow() + timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({'token': token}), 200

# Protected endpoint to check current balance
@app.route('/balance', methods=['GET'])
@token_required
def check_balance(current_user):
    account_id = str(current_user['_id'])
    account = get_account(account_id)
    return jsonify({'account_id': account_id, 'balance': account['balance']}), 200

# Protected endpoint to deposit money
@app.route('/deposit', methods=['POST'])
@token_required
def deposit(current_user):
    account_id = str(current_user['_id'])
    amount = request.json.get('amount')

    if amount <= 0:
        return jsonify({'error': 'Deposit amount must be positive'}), 400

    accounts_collection.update_one(
        {"_id": ObjectId(account_id)},
        {"$inc": {"balance": amount}}
    )

    transaction = {
        "account_id": ObjectId(account_id),
        "type": "deposit",
        "amount": amount,
        "timestamp": datetime.utcnow()
    }
    transactions_collection.insert_one(transaction)

    updated_account = get_account(account_id)
    return jsonify({'account_id': account_id, 'balance': updated_account['balance']}), 200

# Protected endpoint to withdraw money
@app.route('/withdraw', methods=['POST'])
@token_required
def withdraw(current_user):
    account_id = str(current_user['_id'])
    amount = request.json.get('amount')

    if amount <= 0:
        return jsonify({'error': 'Withdrawal amount must be positive'}), 400

    account = get_account(account_id)
    if account['balance'] < amount:
        return jsonify({'error': 'Insufficient funds'}), 400

    accounts_collection.update_one(
        {"_id": ObjectId(account_id)},
        {"$inc": {"balance": -amount}}
    )

    transaction = {
        "account_id": ObjectId(account_id),
        "type": "withdrawal",
        "amount": amount,
        "timestamp": datetime.utcnow()
    }
    transactions_collection.insert_one(transaction)

    updated_account = get_account(account_id)
    return jsonify({'account_id': account_id, 'balance': updated_account['balance']}), 200

# Protected endpoint to transfer money between accounts
@app.route('/transfer', methods=['POST'])
@token_required
def transfer(current_user):
    from_account_id = str(current_user['_id'])
    amount = request.json.get('amount')
    to_account_id = request.json.get('to_account_id')
    to_account_email = request.json.get('to_account_email')

    if amount <= 0:
        return jsonify({'error': 'Transfer amount must be positive'}), 400

    if to_account_id:
        # Try to get the recipient account by ID
        to_account = get_account(to_account_id)
        if not to_account:
            return jsonify({'error': 'Recipient account not found'}), 404
        to_account_id = str(to_account['_id'])
    elif to_account_email:
        # Try to get the recipient account by email
        to_account = get_account(to_account_email)
        if not to_account:
            return jsonify({'error': 'Recipient account not found'}), 404
        to_account_id = str(to_account['_id'])
    else:
        return jsonify({'error': 'Recipient account ID or email is required'}), 400

    from_account = get_account(from_account_id)
    if from_account['balance'] < amount:
        return jsonify({'error': 'Insufficient funds in the source account'}), 400

    # Start a session to perform atomic transactions
    with client.start_session() as session:
        with session.start_transaction():
            # Deduct amount from sender
            accounts_collection.update_one(
                {"_id": ObjectId(from_account_id)},
                {"$inc": {"balance": -amount}},
                session=session
            )
            # Add amount to recipient
            accounts_collection.update_one(
                {"_id": ObjectId(to_account_id)},
                {"$inc": {"balance": amount}},
                session=session
            )
            # Log both transactions
            transfer_out = {
                "account_id": ObjectId(from_account_id),
                "type": "transfer_out",
                "amount": amount,
                "to_account_id": ObjectId(to_account_id),
                "timestamp": datetime.utcnow()
            }
            transfer_in = {
                "account_id": ObjectId(to_account_id),
                "type": "transfer_in",
                "amount": amount,
                "from_account_id": ObjectId(from_account_id),
                "timestamp": datetime.utcnow()
            }
            transactions_collection.insert_many([transfer_out, transfer_in], session=session)

    return jsonify({'message': 'Transfer successful'}), 200

# Protected endpoint to retrieve transaction history
@app.route('/transaction_history', methods=['GET'])
@token_required
def transaction_history(current_user):
    account_id = str(current_user['_id'])

    transactions = list(transactions_collection.find({"account_id": ObjectId(account_id)}).sort("timestamp", -1))
    
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
        transaction['account_id'] = str(transaction['account_id'])
        if "to_account_id" in transaction:
            transaction["to_account_id"] = str(transaction["to_account_id"])
        if "from_account_id" in transaction:
            transaction["from_account_id"] = str(transaction["from_account_id"])
        transaction['timestamp'] = transaction['timestamp'].isoformat()

    return jsonify({'transaction_history': transactions or []}), 200

if __name__ == '__main__':
    app.run(debug=True)
