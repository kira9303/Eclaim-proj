import os

from celery import Celery
import time
import redis
import openai
import json
from dotenv import load_dotenv
#from celery_voice.celery_voice_task import voice_generation
from Logger import Log

celery = Celery('task', broker='redis://redis:6379/0', backend='redis://redis:6379/0')


celery.conf.task_queues = {
    'gpt_queue': {
        'exchange': 'gpt_queue',
        'routing_key': 'gpt_queue',
    }
}

logger = Log("gpt.log")
logger = logger.initialize_logger_handler()

@celery.task(name="task.gpt_service", queue="gpt_queue")
def gpt_service(transcript, streamSid):
    print("printing inside gpt_service task")
    start_time = time.time()

    load_dotenv()

    api_key = os.getenv("GPT_KEY")
    print(f"printing gpt api_key {api_key}")

    openai.api_key = api_key

    function_prompt = "You are an hotel management assistant for Sterling resorts and hotel. Clear any queries user may have about our hotel. Our premium stays start with 5000 rupees which includes dolphin surfing, private jacquzzi and free food throughout the stay. Basic stay on the other hand is of 1500 rupees but does not include dolphin surfing and free food. If the user wants to book a room on call, book it and save the details of booking for the particular date. If user does not specify the date, ask for a date. When you feel like there is nothing more to talk about end the conversation. Keep your response without special symbols, just like normal paragraphs and sentences. Also, in every sentence don't repeat saying hello. Also, please keep your response concise and to the point. Not too much, not too less. Please do not use asterisk symbols like * in your responses. Keep it very short. Also, please don't repeat same words in consecutive responses."


    r = redis.Redis(host='redis', port=6379, db=0)

    #Step 1: get the hashed data redis stored in memory db
    conv_hist_value = r.hget(streamSid, "conv_hist")

    # Step 2: Decode the bytes and load the JSON data into a Python list
    conv_hist_list = json.loads(conv_hist_value.decode('utf-8'))

    conversation_history = [{"role": "system", "content": function_prompt}]
    conversation_history += [
        {"role": "user", "content": msg['user']} if 'user' in msg else {"role": "assistant", "content": msg['ai']}
        for msg in conv_hist_list]

    # Add the new user input to the conversation
    conversation_history.append({"role": "user", "content": transcript})

    # Use the OpenAI API to generate a response
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=conversation_history,
        max_tokens=100,
        temperature=0.2,
        top_p=0.8,
        n=1,
        stop=None
    )

    ai_response = response.choices[0].message['content'].strip()

    logger.info(f"printing the AI response generated: {ai_response}")
    #print(f"printing the AI response generated: {ai_response}")

    # Add the new interaction to the chat history
    conv_hist_list.append({'user': transcript, 'ai': ai_response})

    updated_conv_hist = json.dumps(conv_hist_list)

    # Store the updated conversation history back in Redis using hset
    r.hset(streamSid, "conv_hist", updated_conv_hist)

    #voice_generation.apply_async((ai_response, streamSid), queue='voice_queue')

    task = celery.send_task(
        "newtask.voice_generation",
        args=[ai_response, streamSid],
        queue='voice_queue'
    )


    end_time = time.time()
    resp_time = end_time - start_time
    logger.info(f"Time taken for the gpt service to execute was: {resp_time}")
    #print(f"Time taken to execute the entire task is: {resp_time}")
    #print("bypassed sleep time")