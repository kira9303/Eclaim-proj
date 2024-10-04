from deepgram import DeepgramClientOptions, DeepgramClient, LiveOptions, LiveTranscriptionEvents
import asyncio
import os
#from celery_gpt_service.celery_tasks import gpt_service

from celery import Celery

trans_celery = Celery('sendtollm', broker='redis://redis:6379/0', backend='redis://redis:6379/0')


class DeepgramTranscription:
    def __init__(self, ws, API_KEY, streamsid):
        self.ws = ws
        self.api_key = API_KEY
        self.streamsid = streamsid


    async def connect(self):
        config = DeepgramClientOptions(
            options={"keepalive": "true"}
        )

        # Create a websocket connection using the DEEPGRAM_API_KEY from environment variables
        deepgram = DeepgramClient(self.api_key, config)

        #some = deepgram.listen.l

        # Use the listen.live class to create the websocket connection
        dg_connection = deepgram.listen.asyncwebsocket.v("1")

        #print(dg_connection)

        options = LiveOptions(
            punctuate=True,
            interim_results=False,
            language='en',
            smart_format=True,
            encoding="mulaw",
            channels=1,
            sample_rate=8000,
            endpointing=2000,
            model= "nova-2",
            no_delay=True
        )

        dg_connection.on(LiveTranscriptionEvents.Transcript, self.on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, self.on_error)

        await dg_connection.start(options)

        return dg_connection

    async def on_message(self, *args, **kwargs):
        #print(f"printing args first: {args}")
        #print(f"printing kwargs now: {kwargs}")
        result = kwargs.get('result') or args[0]
        if(result.is_final):
            sentence = result.channel.alternatives[0].transcript
            if len(sentence) == 0:
                return

        #write the celery transfer script
            #gpt_service.delay(sentence, self.streamsid)

            task = trans_celery.send_task(
                "task.gpt_service",
                args=[sentence, self.streamsid],
                queue='gpt_queue'
            )

            print(f"Transcription: {sentence}, StreamSid: {self.streamsid}")
        print("done transcription")

    async def on_error(self, error, **kwargs):
        print(f"Error: {error}")







