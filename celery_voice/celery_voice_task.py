import os

from celery import Celery, shared_task
import time

from dotenv import load_dotenv
import base64
import requests
import websockets as web
#import pyaudio
from cartesia import Cartesia
import asyncio
import json
import websocket
import threading
#import rel
import aioredis



voice_celery = Celery('newtask', broker='redis://redis:6379/0', backend='redis://redis:6379/0')

voice_celery.conf.task_queues = {
    'default': {
        'exchange': 'default',
        'routing_key': 'default',
    },
    'voice_queue': {
        'exchange': 'voice_queue',
        'routing_key': 'voice_queue',
    }
}

load_dotenv()
voice_key = os.getenv("CARTESIA_KEY")


#client = AsyncCartesia(api_key=voice_key)


class WebSocketClient:
    def __init__(self, url):
        self.url = url
        self.ws = None
        self.keep_alive = True

    def on_open(self, ws):
        print("WebSocket connection opened.")
        threading.Thread(target=self.send_keep_alive, daemon=True).start()

    def on_message(self, ws, message):
        print(f"Received message from server: {message}")

    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket connection closed: {close_status_code}, {close_msg}")
        self.keep_alive = False

    def send_keep_alive(self):
        while self.keep_alive:
            try:
                print("Sending ping to keep connection alive...")
                self.ws.send("ping")
            except Exception as e:
                print(f"Error sending ping: {e}")
            time.sleep(1)  # Ping every 30 seconds

    def run(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

    def send_data(self, data):
        if self.ws and self.keep_alive:
            try:
                self.ws.send(data)
                print(f"Sent data: {data}")
            except Exception as e:
                print(f"Failed to send data: {e}")

    def close(self):
        if self.ws:
            self.ws.close()
            self.keep_alive = False
            print("WebSocket connection closed manually.")




async def connect_handler(url, gpt_response, streamSid):

    r = aioredis.from_url("redis://redis:6379/0", decode_responses=True)
    voice_q = await r.hget(streamSid, "voice_q")

    if(voice_q == "False"):
        async with web.connect(url) as ws_twilio:

            value = "True"

            await r.hset(streamSid, "voice_q", value)

            client = Cartesia(api_key=voice_key)
            indian_lady = "3b554273-4299-48b9-9aaf-eefd438e3941"

            voice = client.voices.get(id=indian_lady)

            output_format = {
                "container": "raw",
                "encoding": "pcm_mulaw",
                "sample_rate": 8000,
            }

            model_id = "sonic-english"

            cart_ws = client.tts.websocket()

            # ws = twilio_connect["current"]

            # Generate and stream audio using the websocket
            for output in cart_ws.send(
                    model_id=model_id,
                    transcript=gpt_response,
                    voice_embedding=voice["embedding"],
                    stream=True,
                    output_format=output_format,
            ):
                buffer = output["audio"]

                encoded_string = base64.b64encode(buffer).decode('utf-8')
                # print(encoded_string)

                json_dict = {
                    "streamid": streamSid,
                    "audio": encoded_string
                }

                await ws_twilio.send(json.dumps(json_dict))

            await ws_twilio.close()

            await r.hset(streamSid, "voice_q", "False")



            r.close()
    if(voice_q == "True"):
        r.close()
        return


@voice_celery.task(name='newtask.voice_generation', queue='voice_queue')
def voice_generation(gpt_response, streamSid):

    voice_start_time = time.time()

    asyncio.run(connect_handler("ws://fastapi_service:8000/send_voice", gpt_response, streamSid))

    end_voice_time = time.time()
    total_voice_time = end_voice_time - voice_start_time
    print(f"time taken for voice service: {total_voice_time}")




async def generate_audio(transcript, streamid):
    client = AsyncCartesia(api_key=voice_key)
    seduc_bitch = "03496517-369a-4db1-8236-3d3ae459ddf7"

    voice = client.voices.get(id=seduc_bitch)

    output_format = {
        "container": "raw",
        "encoding": "pcm_mulaw",
        "sample_rate": 8000,
    }

    model_id = "sonic-english"

    output = await client.tts.sse(
        model_id=model_id,
        transcript=transcript,
        voice_embedding=voice["embedding"],
        stream=False,
        output_format=output_format,
    )

    buffer = output["audio"]

    encoded_string = base64.b64encode(buffer).decode('utf-8')
    # print(encoded_string)

    json_dict = {
        "streamid": streamid,
        "audio_enc": encoded_string
    }

    headers = {'Content-Type': 'application/json'}

    response = requests.post("http://localhost:8000/send_audio", json=json_dict, headers=headers)

    print("Status Code:", response.status_code)




