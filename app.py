import aiohttp
import asyncio
import json
import time

# URLs
API_URL = "https://api.xalyon.xyz/v2/atom/index.php?endpoint=admin_view"
CLAIM_LIST_URL = "https://store.atom.com.mm/mytmapi/v1/my/point-system/claim-list"
CLAIM_URL = "https://store.atom.com.mm/mytmapi/v1/my/point-system/claim"
DASHBOARD_URL = "https://store.atom.com.mm/mytmapi/v1/my/dashboard"

# Backup file
BACKUP_FILE = "backup.json"

COMMON_HEADERS = {
    "User-Agent": "MyTM/4.11.0/Android/30",
    "X-Server-Select": "production",
    "Device-Name": "Xiaomi Redmi Note 8 Pro"
}

async def fetch_json_data(session):
    """Fetch JSON data from the API and save to backup.json."""
    print("Fetching JSON data from API...")
    try:
        async with session.get(API_URL) as response:
            if response.status == 200:
                data = await response.json()
                with open(BACKUP_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                print("JSON data fetched and saved to backup.json.")
                return data
            print(f"Failed to fetch JSON data. HTTP Code: {response.status}")
            return None
    except Exception as e:
        print(f"Error fetching JSON data: {str(e)}")
        return None

async def get_claimable_id(session, access_token, msisdn, userid):
    """Get claimable ID from claim-list endpoint"""
    params = {
        "msisdn": msisdn.replace("%2B959", "+959"),
        "userid": userid,
        "v": "4.11.0"
    }
    
    headers = {**COMMON_HEADERS, "Authorization": f"Bearer {access_token}"}

    try:
        async with session.get(CLAIM_LIST_URL, params=params, headers=headers) as response:
            if response.status == 200:
                json_data = await response.json()
                attributes = json_data.get("data", {}).get("attribute", [])
                
                for attribute in attributes:
                    if attribute.get("enable", False):
                        return str(attribute.get("id", "no"))
                return "no"
            print(f"[Claim List] {msisdn}: Failed to get claim list - Status {response.status}")
            return "error"
    except Exception as e:
        print(f"[Claim List] Error for {msisdn}: {str(e)}")
        return "error"

async def process_claim(session, access_token, msisdn, userid, claim_id):
    """Process the actual claim with retrieved ID"""
    params = {
        "msisdn": msisdn.replace("%2B959", "+959"),
        "userid": userid,
        "v": "4.11.0"
    }
    
    headers = {**COMMON_HEADERS, "Authorization": f"Bearer {access_token}"}
    payload = {"id": int(float(claim_id))}  # Handle Java's double parsing logic

    try:
        async with session.post(CLAIM_URL, params=params, json=payload, headers=headers) as response:
            response_text = await response.text()
            status = "Success" if response.status == 200 else "Failed"
            print(f"[Claim] {msisdn}: {status} - Response: {response_text}")
            return status == "Success"
    except Exception as e:
        print(f"[Claim] Error for {msisdn}: {str(e)}")
        return False

async def handle_claim(session, item):
    """Handle complete claim flow for a single item"""
    msisdn = item["phone"]
    access_token = item["access"]
    userid = item["userid"]
    
    # First get claimable ID
    claim_id = await get_claimable_id(session, access_token, msisdn, userid)
    
    if claim_id == "no":
        print(f"[Claim] {msisdn}: No available claims")
        return False
    if claim_id == "error":
        print(f"[Claim] {msisdn}: Error checking claims")
        return False
    
    # If valid ID found, process claim
    return await process_claim(session, access_token, msisdn, userid, claim_id)

async def send_dashboard_request(session, item):
    """Send dashboard request with custom headers"""
    params = {
        "isFirstTime": "1",
        "isFirstInstall": "0",
        "msisdn": item["phone"].replace("%2B959", "+959"),
        "userid": item["userid"],
        "v": "4.11.0"
    }
    
    headers = {**COMMON_HEADERS, "Authorization": f"Bearer {item['access']}"}

    try:
        async with session.get(DASHBOARD_URL, params=params, headers=headers) as response:
            response_text = await response.text()
            status = "Success" if response.status == 200 else "Failed"
            print(f"[Dashboard] {item['phone']}: {status} - Response: {response_text}")
    except Exception as e:
        print(f"[Dashboard] Error for {item['phone']}: {str(e)}")

async def main():
    """Main function to handle API requests in sequence."""
    async with aiohttp.ClientSession() as session:
        json_data = await fetch_json_data(session)
        if not json_data:
            print("No data to process. Exiting...")
            return

    async with aiohttp.ClientSession() as session:
        # Process all dashboard requests first
        print("\nStarting dashboard requests...")
        dashboard_tasks = [send_dashboard_request(session, item) for item in json_data]
        await asyncio.gather(*dashboard_tasks)
        print("\nAll dashboard requests completed!")

        # Process claims sequentially per user
        print("\nStarting claim processes...")
        claim_tasks = [handle_claim(session, item) for item in json_data]
        await asyncio.gather(*claim_tasks)
        print("\nAll claim processes completed!")

if __name__ == "__main__":
    start_time = time.time()
    print("Script execution started...")
    
    try:
        loop = asyncio.get_running_loop()
        loop.run_until_complete(main())
    except RuntimeError:
        asyncio.run(main())

    print(f"\nTotal execution time: {time.time() - start_time:.2f} seconds")
    print("Script execution completed.")
