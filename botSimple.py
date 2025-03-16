import discord
import requests
import json
import os

DISCORD_TOKEN = "Discord Token Here"
AI_MODEL = "ollama AI model"
SYSTEM_PROMPT = "System prompte here (for example be friendly)"


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def ask_ollama(prompt: str, model_name: str, system_prompt: str = ""):
    headers = {
        'Content-Type': 'application/json',
    }
    data = {
        "prompt": prompt,
        "model": model_name,
        "temperature": 0.7,
        "max_tokens": 100,
        "system": system_prompt  # Add system prompt here
    }

    try:
        response = requests.post(f"http://localhost:11434/api/generate", headers=headers, json=data, stream=True)
        response.raise_for_status()

        response_data = ""

        for line in response.iter_lines():
            if line:
                try:
                    line_data = line.decode("utf-8")
                    line_json = json.loads(line_data)
                    
                    if 'response' in line_json and line_json['response']:
                        response_data += line_json['response']

                    if 'done' in line_json and line_json['done']:
                        break
                except Exception as e:
                    print(f"Error parsing line: {e}")

        return response_data.strip() if response_data else "Error: No response from model."
    except requests.exceptions.Timeout:
        return "Error: Request timed out."
    except requests.exceptions.RequestException as e:
        return f"Error: {str(e)}"

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.content.startswith('.ask'):
        prompt = message.content[len('.ask '):]
        
        # Send a "thinking..." message
        thinking_message = await message.channel.send("Thinking...")

        # Get the response from Ollama API
        response = ask_ollama(prompt, AI_MODEL, SYSTEM_PROMPT)

        # Split the response into chunks of 2000 characters if needed
        if len(response) > 2000:
            # Split into chunks of 2000 characters
            for i in range(0, len(response), 2000):
                chunk = response[i:i+2000]
                await message.channel.send(chunk)
            # Edit the thinking message with a message indicating the response was sent
            await thinking_message.edit(content="Response sent in parts.")
        else:
            # Edit the "thinking..." message with the actual response
            await thinking_message.edit(content=response)

    elif message.content.startswith('.help'):
        await message.channel.send("**.ask** for chatting with bot")
client.run(DISCORD_TOKEN)
