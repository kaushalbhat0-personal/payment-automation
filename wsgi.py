from app import create_app

# load_dotenv runs inside create_app(); check logs for
# "SKIP_WEBHOOK_VERIFY from environment: ..." after startup.
app = create_app()
