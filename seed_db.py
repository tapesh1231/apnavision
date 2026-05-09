import os
from app import create_app, db
from app.models import Scooter, User, Offer

app = create_app()

def seed():
    with app.app_context():
        # Drop and recreate all tables
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()

        # Create admin user
        admin = User(username="testuser", email="test@example.com", is_admin=True)
        admin.set_password("password123")
        db.session.add(admin)

        # Create scooters
        scooters = [
            Scooter(
                name="Volt Commuter", 
                category="Commuter",
                description="The perfect balance of weight and performance for your daily city commutes. Features solid tires and regenerative braking.", 
                price=499.99, 
                top_speed=15, 
                range=20, 
                battery_life="4 hours", 
                stock_quantity=50,
                image_url="https://images.unsplash.com/photo-1595822920406-b66991ce6ab0?auto=format&fit=crop&q=80&w=800"
            ),
            Scooter(
                name="Volt Pro", 
                category="Performance",
                description="High performance dual-motor scooter for enthusiasts. Features full suspension and hydraulic brakes for maximum safety at high speeds.", 
                price=899.99, 
                top_speed=25, 
                range=40, 
                battery_life="6 hours", 
                stock_quantity=20,
                image_url="https://images.unsplash.com/photo-1593121528659-e93bfa59dd33?auto=format&fit=crop&q=80&w=800"
            ),
            Scooter(
                name="Volt Off-Road", 
                category="Off-Road",
                description="Built for tough terrains and dirt trails. Comes with 11-inch pneumatic off-road tires and dual shock absorbers.", 
                price=1199.99, 
                top_speed=35, 
                range=50, 
                battery_life="8 hours", 
                stock_quantity=10,
                image_url="https://images.unsplash.com/photo-1598108520849-519656ebac10?auto=format&fit=crop&q=80&w=800"
            )
        ]
        db.session.bulk_save_objects(scooters)
        db.session.commit()
        
        print("Successfully recreated and seeded the database with admin user and placeholder scooters!")

if __name__ == "__main__":
    seed()
