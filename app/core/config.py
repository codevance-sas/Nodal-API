import os
import dotenv
dotenv.load_dotenv()

class Settings():
    SECRET_KEY: str = os.getenv('SECRET_KEY')
    GOOGLE_CLIENT_ID: str = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET: str = os.getenv('GOOGLE_CLIENT_SECRET')
    JWT_SECRET_KEY: str = os.getenv('JWT_SECRET_KEY')
    REDIRECT_URL: str = 'http://localhost:8000/api/auth/callback'
    FRONTEND_URL: str = 'http://localhost:3000'

    class Config:
        env_file = '.env'

settings = Settings()
