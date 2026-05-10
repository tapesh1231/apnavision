from app import create_app, db
app = create_app()
with app.app_context():
    db.session.execute(db.text('ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE'))
    db.session.execute(db.text('ALTER TABLE users ADD COLUMN profile_photo_url VARCHAR(256)'))
    db.session.execute(db.text('ALTER TABLE users ADD COLUMN phone_number VARCHAR(32)'))
    db.session.commit()
    print("Columns added successfully.")
