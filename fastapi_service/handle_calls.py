from dotenv import load_dotenv
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from fastapi.responses import HTMLResponse
from typing import Optional
import aioredis
import asyncio
import json
import os
import requests
import base64
from urllib.parse import parse_qs, urlparse
from transcription.transcription_service import DeepgramTranscription
#import transcription
import uuid
from deepgram import LiveTranscriptionEvents, LiveOptions
from Logger import Log



app = FastAPI()

load_dotenv()

api_key = os.getenv("DEEPGRAM_KEY")

# Redis configuration
REDIS_HOST = "redis"
REDIS_PORT = 6379
REDIS_DB = 0

global connections

connections = {}

# Initialize Redis connection
redis = aioredis.from_url(f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}", decode_responses=True)

print(redis)


#writing the logger code:-
logger = Log('handler.log')
logger = logger.initialize_logger_handler()



@app.api_route("/sock.xml", methods=["GET", "POST"])
async def serve_twiml(request: Request):
    if request.method == "POST":
        logger.info("Received a POST request to /sock.xml")
        #print("Received a POST request to /sock.xml")

    # Serve the TwiML file
    file_path = os.path.join("xml_files", "sock.xml")

    #file_path = os.path.abspath(os.path.join("", "sock.xml"))

    if not os.path.exists(file_path):
        raise RuntimeError(f"File at path {file_path} does not exist.")
    logger.exception("Caught a runtime error")
    return FileResponse(path=file_path, filename="sock.xml")

@app.api_route("/custom_agent", methods=["POST"])
async def custom_agent_serve(request: Request):
    if(request == "POST"):
        logger.info("Inside the /custom_agent endpoint")

        get_data = await request.json()
        logger.info(f"awaited retrieval of JSON from the recieved request. JSON:- {get_data}")
        phone_numbers = get_data["phone_numbers"]
        function_prompt = get_data["custom_prompt"]




@app.api_route("/get_call_data", methods=["POST"])
async def get_data_to_call(request: Request):
    #initialize a global variable here
    if request.method == "POST":
        logger.info("inside get_call_data to store the data")
        #print("inside get_call_data")
        #initiate the call here after getting the data along with the prompt
    return "success", 200

@app.api_route("/send_audio", methods=["POST"])
async def get_voice_data(request: Request):
    if request.method == "POST":
        logger.info("inside send_audio, sending the audio back to the end user using POST request")
        #print("inside send_audio")

        data = await request.json()

        # Extract audio and streamSid from the JSON
        audio_enc = data.get("audio_enc")
        streamid = data.get("streamid")

        cur_ws = connections[streamid]["twilio_ws"]
        logger.info(f"printing the ret websocket object in /send_audio (POST request) {cur_ws}")

        try:
            # Example of sending JSON data using send_text
            await cur_ws.send_text(json.dumps({
                "streamSid": streamid,
                "event": "media",
                "media": {
                    "payload": audio_enc
                }
            }))
        except Exception as e:
            logger.exception(f"exception occured in /send_audio. Exception: {e}")
            #print(f"Error sending message: {e}")


    return "success", 200

@app.websocket("/send_voice")
async def send_voice_enpoint(websocket: WebSocket):

    logger.info("inside /send_voice, trying to wait for the connection")
   # print("inside voice_endpoint, trying to wait for the connection")
    await websocket.accept()
    logger.info("awaited connection for /send_voice")
    #print("awaited the connection for voice_endpoint")


    try:
        while True:

            data = await websocket.receive()
            #logger.info("printing the ")
            #print("prnting the full data recieved:- ")

            loaded_data = json.loads(data["text"])
            logger.info("logging text data")

            audio = loaded_data["audio"]
            streamid = loaded_data["streamid"]


            cur_ws = connections[streamid]["twilio_ws"]

            try:
                # Example of sending JSON data using send_text
                await cur_ws.send_text(json.dumps({
                    "streamSid": streamid,
                    "event": "media",
                    "media": {
                        "payload": audio
                    }
                }))
            except Exception as e:
                logger.exception(f"Exception occured in /send_voice. Exception: {e}")
                #print(f"Error sending message: {e}")

    except WebSocketDisconnect or RuntimeError:
        logger.exception("closing websocket connection. RuntimeError or WebSocketDisconnect")
        #print(f"Connection closed voice: ")
        # Remove the disconnected WebSocket from Redis
        #await redis.delete(f"room:{call_sid}")




@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):

    logger.info("inside /ws endpoint, trying to wait for the connection")
    #print("inside endpoint, trying to wait for the connection")
    await websocket.accept()
    logger.info("awaited the /ws connection")
    #print("awaited the connection")

    data = await websocket.receive()

    # if data is recieved
    if 'text' in data:

        rec_data = json.loads(data['text'])
        logger.info(f"Logging the initial data recieved: {rec_data}")
    else:
        return
    #print("printing the initial data: {}".format(rec_data))

    try:
        while True:
            # Receive audio data from Twilio
            data = await websocket.receive()

            #new_data = json.dumps(data['text'])

            #if data is recieved

            if 'text' in data:

                rec_data = json.loads(data['text'])
                logger.info(f"Logging the in loop data recieved: {rec_data}")
            else:
                logger.info(f"KeyError: 'text' not there in data recieved, returning back")
                return
            rec_data = json.loads(data['text'])

            #print("printing converted data")
            #print(rec_data)

            if rec_data["event"] == "connected":
                logger.info("stream established, event: connected recieved")
                temp_data = rec_data["event"]
                logger.info(f"Printing CallSid, inside Connected Event: {temp_data}")




            if rec_data['event'] == "start":
                streamsid = rec_data["streamSid"]
                call_sid = rec_data['start']['callSid']

                #find if the callSid exists in the redis-db. If yes, replace it with the st

                logger.info("Inside event: Start. Trying connecting deepgram via websocket")
                dcon = DeepgramTranscription(websocket, api_key, streamsid)
                dg_connection = await dcon.connect()
                logger.info("Awaited Deepgram connection via websockets")


                #print("connection established with deepgram websocket:- ")

                dump_data = {

                    "twilio_ws": websocket,
                    "dg_ws": dg_connection,
                    "dg_obj": dcon

                }

                redis_dump = {
                    "conv_hist": json.dumps([]),
                    "callSid": call_sid,
                    "voice_q": "False"
                }

                connections[f"{streamsid}"] = dump_data

                logger.info(f"The connections dict is: {connections}")
                #print(f"printing connections dict: {connections}")

                await redis.hset(f"{streamsid}", mapping=redis_dump)

                logger.info("added streamsid and corresponding data in Redis")
                logger.info("Also added websocket connection objects to in-memory global variable")


            if rec_data['event'] == "media":
                payload_b64 = rec_data['media']['payload']
                payload_mulaw = base64.b64decode(payload_b64)

                stream_sid = rec_data["streamSid"]

                dg_connection = connections[f"{stream_sid}"]['dg_ws']


                await dg_connection.send(payload_mulaw)


            if rec_data['event'] == "stop":

                #deleting the entry for the particular streamID stored when it recieved a "stop" event
                key_name = rec_data["streamSid"]
                redis.delete(key_name)

                logger.info(f"deleted the streamSid from redis: {key_name}")

                #print(f"deleted the streamSid from redis: {key_name}")
                logger.info("twilio transcription should stop now")
                #print("twilio transcription should stop now")
                #print("have to clean")

    except WebSocketDisconnect:
        logger.info(f"connection closed web socket:")

        #print(f"Connection closed main: ")
        # Remove the disconnected WebSocket from Redis
        #await redis.delete(f"room:{call_sid}")



# Example usage
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)




