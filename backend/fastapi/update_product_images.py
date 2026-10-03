from sqlalchemy import text
from database import engine

images = {
    "Wireless Mouse": "https://images.unsplash.com/photo-1527814050087-3793815479db?auto=format&fit=crop&w=900&q=82",
    "Wireless Keyboard": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=82",
    "Bluetooth Speaker": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=82",
    "USB-C Charger": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=82",
    "Gaming Headset": "https://images.unsplash.com/photo-1599669454699-248893623440?auto=format&fit=crop&w=900&q=82",
    "Laptop Backpack": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=82",
    "Smart Watch": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=82",
    "Mechanical Keyboard": "https://images.unsplash.com/photo-1511467687858-23d090aaee0d?auto=format&fit=crop&w=900&q=82",
    "Phone Stand": "https://images.unsplash.com/photo-1512499617640-c74ae3a79d37?auto=format&fit=crop&w=900&q=82",
    "Power Bank": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?auto=format&fit=crop&w=900&q=82",
    "Air Conditioner": "https://images.unsplash.com/photo-1631545806609-5e4fbc7ecf00?auto=format&fit=crop&w=900&q=82",
    "Refrigerator": "https://images.unsplash.com/photo-1571175443880-49e1d587d4f4?auto=format&fit=crop&w=900&q=82",
    "Washing Machine": "https://images.unsplash.com/photo-1626806787461-102c1bfaaea1?auto=format&fit=crop&w=900&q=82",
    "Coffee Maker": "https://images.unsplash.com/photo-1517668808822-9ebb02f2a0e6?auto=format&fit=crop&w=900&q=82",
    "Electric Kettle": "https://images.unsplash.com/photo-1594212699903-ec8a3eca50f5?auto=format&fit=crop&w=900&q=82",
    "Desk Lamp": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=82",
    "Office Chair": "https://images.unsplash.com/photo-1541558869434-2840d308329a?auto=format&fit=crop&w=900&q=82",
    "Study Table": "https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=900&q=82",
    "Travel Trolley": "https://images.unsplash.com/photo-1565026057447-bc90a3dceb87?auto=format&fit=crop&w=900&q=82",
    "Yoga Mat": "https://images.unsplash.com/photo-1592432678016-e910b452f9a2?auto=format&fit=crop&w=900&q=82",
}

with engine.begin() as connection:
    for name, image_url in images.items():
        result = connection.execute(
            text("""
                UPDATE products
                SET image = :image_url
                WHERE name = :name
                  AND (image IS NULL OR image = '')
            """),
            {
                "name": name,
                "image_url": image_url,
            },
        )

        print(f"{name}: updated {result.rowcount} row(s)")

print("\nImage update completed.")