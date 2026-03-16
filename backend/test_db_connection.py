import asyncio
import os
import sys
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load the environment variables
# Assuming the script runs from the backend directory, so .env is one level up
load_dotenv(dotenv_path="../.env")

async def test_mongodb_connection():
    print("Testing MongoDB connection...")
    
    # Get configuration from environment variables
    mongo_url = os.environ.get("MONGODB_URL")
    database_name = os.environ.get("MONGODB_DATABASE", "pantry_db")
    
    if not mongo_url:
        print("❌ Error: MONGODB_URL environment variable is not set.")
        print("Please check your .env file.")
        sys.exit(1)
        
    print(f"Connecting to database: {database_name}")
    
    try:
        # Initialize the motor client
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
        
        # Issue a ping command to verify the connection
        print("Pinging database...")
        await client.admin.command("ping")
        
        # Try to access the specified database
        db = client[database_name]
        
        # Test listing collections (does not require writing)
        collections = await db.list_collection_names()
        
        print("\n✅ Success! Connected to MongoDB.")
        print(f"✅ Authenticated successfully.")
        print(f"✅ Found {len(collections)} collections in '{database_name}':")
        for col in collections:
            print(f"   - {col}")
            
    except Exception as e:
        print("\n❌ Failed to connect to MongoDB.")
        print(f"Error details: {e}")
        sys.exit(1)
    finally:
        # Clean up
        if 'client' in locals():
            client.close()
            print("\nConnection closed.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(test_mongodb_connection())
