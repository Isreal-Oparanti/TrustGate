import asyncio
from app.services.agentic_verification import tool_google_maps

async def run_map_test():
    print("Testing map logic (Nominatim)...")
    
    addresses = [
        "22 Bode Thomas Street, Surulere, Lagos",
        "15 Adeniran Ogunsanya, Surulere, Lagos",
        "Aso Rock, Abuja",
        "Fake Address That Does Not Exist 123456789, Somewhere"
    ]
    
    for address in addresses:
        print(f"\n--- Testing Address: {address} ---")
        result = await tool_google_maps(address)
        print(f"Status: {result.status}")
        print(f"Provider: {result.provider}")
        print(f"Confidence: {result.confidence}")
        print(f"Data: {result.data}")
        print(f"Flags generated: {len(result.flags)}")
        for f in result.flags:
            print(f"  - Flag: {f.flag_type} ({f.severity}) - {f.detail}")

if __name__ == "__main__":
    asyncio.run(run_map_test())
