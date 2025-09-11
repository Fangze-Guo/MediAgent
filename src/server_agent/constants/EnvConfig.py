import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DASHSCOPE_API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")

MCP_SERVERS = os.getenv("MCP_SERVERS")