import discord
import requests
import json
import os
import re
from datetime import datetime
import asyncio  # Added for rate limit handling

# Configuration
DISCORD_TOKEN = "Discord token"  # Replace with your bot token
MODEL_NAME = "AI model"    # Model to use for Ollama API
SHOW_THINK_SECTION = False  # Set to False to hide the <think></think> section. Only function on Deepseek model. When False Think will not be displayed. Othervise Think will be in spoiler
CHAT_HISTORY_FILE = "chat_history.json"    # File to store short-term chat history. Default is same as bot location
LONG_TERM_MEMORY_FILE = "long_term_memory.json"  # File to store long-term memory. Default is same as bot location
MAX_HISTORY_MESSAGES = 20                  # Number of messages to remember per user
DISCLAIMER_MESSAGE = "⚠️ **Disclaimer:** This bot stores chat history to provide context-aware responses. By using this bot, you agree to your messages being stored."

# System prompts - Behaviour of AI chat bot
CHAT_SYSTEM_PROMPT = """
You are a friendly and empathetic chatbot named NightshowStarAI. Your goal is to provide helpful, engaging, and human-like responses. Use emojis to make your responses more expressive. Keep your answers concise but informative.

Rules:
1. Always address the user by their name if you know it.
2. Use the information you have about the user to provide personalized responses, but NEVER mention "memory," "data," or "long-term memory."
3. If the user asks about themselves, share what you know about them in a natural way, as if you're recalling it from a conversation.
4. If you don't know something about the user, ask them to share more information in a friendly way.

Example 1:
User: "What do you know about me?"
Response: "😊 Well, Swit, I know you're a warm-hearted person who loves playing D&D. You're also a Ranger in Nova Terra, which means you're resourceful and determined. Is there anything else you'd like to share?"

Example 2:
User: "Tell me about Lojza."
Response: "🤖 Lojza is a software engineering student at SPST. They're fascinated by quantum physics and own 8 computers. They're also a big fan of The Big Bang Theory! 😊"

Example 3:
User: "I don't think you know me."
Response: "😊 You're right, I don't know much about you yet. But I'd love to learn! What's your name, and what are your interests?"
"""

#EXTRACTION_SYSTEM_PROMPT - Don't edit unless AI is not returning valid JSON.
EXTRACTION_SYSTEM_PROMPT = """
You are an information extraction assistant. Your task is to extract important information about users from the conversation, such as their names, preferences, or key facts. Focus only on information that is specific to the user and avoid general knowledge.

Rules:
1. Always extract the user's name if mentioned.
2. Extract specific preferences, interests, or facts about the user.
3. If the user mentions another person, extract their name and any relevant information about them.
4. If no name is mentioned, associate the extracted information with the current user.
5. Return the information in JSON format with keys like "name", "preference", or "fact".

Example 1:
User: "My name is Alex, and I love reading fantasy novels."
Output:
{
    "name": "Alex",
    "preference": "loves reading fantasy novels"
}

Example 2:
User: "I'm working on a project called USB Raid Array."
Output:
{
    "project": "USB Raid Array"
}

Example 3:
User: "My friend Lojza is a software engineering student."
Output:
{
    "name": "Lojza",
    "fact": "software engineering student"
}

If no user-specific information is found, return an empty JSON object: {}
"""


# Load short-term chat history from file
def load_chat_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "r") as file:
            return json.load(file)
    return {}

# Save short-term chat history to file
def save_chat_history(chat_history):
    with open(CHAT_HISTORY_FILE, "w") as file:
        json.dump(chat_history, file, indent=4)

# Load long-term memory from file
def load_long_term_memory():
    if os.path.exists(LONG_TERM_MEMORY_FILE):
        with open(LONG_TERM_MEMORY_FILE, "r") as file:
            return json.load(file)
    return {"bot": {}, "name_to_id": {}}  # Initialize with a "bot" section and a name-to-ID mapping

# Save long-term memory to file
def save_long_term_memory(long_term_memory):
    with open(LONG_TERM_MEMORY_FILE, "w") as file:
        json.dump(long_term_memory, file, indent=4)

# Function to ask Ollama
def ask_ollama(prompt: str, system_prompt: str = "", chat_history=None, long_term_memory: dict = None):
    headers = {
        'Content-Type': 'application/json',
    }
    
    # Include long-term memory and chat history in the prompt
    full_prompt = ""
    
    # Add bot's long-term memory (if available)
    if long_term_memory and "bot" in long_term_memory:
        bot_memory_context = "\n".join([f"{key}: {value}" for key, value in long_term_memory["bot"].items()])
        full_prompt += f"Bot's Long-Term Memory:\n{bot_memory_context}\n\n"
    
    # Add user's long-term memory (if available)
    if long_term_memory:
        for user_id, memory in long_term_memory.items():
            if user_id != "bot" and user_id != "name_to_id":  # Skip the bot's memory and name-to-ID mapping
                memory_context = "\n".join([f"{key}: {value}" for key, value in memory.items()])
                full_prompt += f"Long-Term Memory for User {user_id}:\n{memory_context}\n\n"
    
    # Add chat history (if provided)
    if chat_history:
        if isinstance(chat_history, str):
            # If chat_history is a string, use it directly
            full_prompt += f"Chat History:\n{chat_history}\n\n"
        elif isinstance(chat_history, list):
            # If chat_history is a list, format it
            context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
            full_prompt += f"Chat History:\n{context}\n\n"
    
    # Add the current user prompt
    full_prompt += f"User: {prompt}"
    
    # Prepare the data for the Ollama API request
    data = {
        "prompt": full_prompt,
        "model": MODEL_NAME,  # Use the configured model
        "temperature": 0.7,
        "max_tokens": 100,
        "system": system_prompt
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

# Function to extract important information from user input only
def extract_important_info(prompt: str):
    data = {
        "prompt": f"User: {prompt}",
        "model": MODEL_NAME,  # Use the configured model
        "temperature": 0.5,
        "max_tokens": 100,
        "system": EXTRACTION_SYSTEM_PROMPT
    }
    
    try:
        # Send the request to Ollama
        response = requests.post(
            "http://localhost:11434/api/generate",
            headers={'Content-Type': 'application/json'},
            json=data,
            stream=True
        )
        response.raise_for_status()
        
        # Process the streaming response
        response_data = ""
        for line in response.iter_lines():
            if line:
                try:
                    line_data = line.decode("utf-8")
                    line_json = json.loads(line_data)
                    
                    if 'response' in line_json:
                        response_data += line_json['response']
                    
                    if 'done' in line_json and line_json['done']:
                        break
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                    continue
        
        print("Raw response from Ollama:", response_data)  # Debug: Print raw response
        
        # Use regex to find all JSON-like blocks
        json_blocks = re.findall(r'\{.*?\}', response_data, re.DOTALL)
        
        # Try to parse each JSON-like block
        extracted_infos = []
        for block in json_blocks:
            try:
                # Remove comments and invalid characters
                block = re.sub(r'//.*?\n', '', block)  # Remove comments
                block = re.sub(r'/\*.*?\*/', '', block, flags=re.DOTALL)  # Remove block comments
                block = block.strip()
                
                # Parse the JSON block
                extracted_info = json.loads(block)
                print("Extracted info:", extracted_info)  # Debug: Print extracted info
                extracted_infos.append(extracted_info)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON block: {e}")
                continue
        
        if not extracted_infos:
            print("No valid JSON found in the response.")
        return extracted_infos
    except Exception as e:
        print(f"Error extracting important info: {e}")
    return []

# Function to extract user ID from a mention
def extract_user_id_from_mention(mention: str):
    # Extract the user ID from a Discord mention (e.g., <@123456789012345678> or <@!123456789012345678>)
    match = re.match(r'<@!?(\d+)>', mention)
    if match:
        return match.group(1)
    return None

# Function to process the <think></think> section
# Function to process the <think></think> section
def process_think_section(response: str):
    if SHOW_THINK_SECTION:
        # Replace <think> and </think> with spoiler tags (||)
        response = response.replace("<think>", "||").replace("</think>", "||")
    else:
        # Remove everything between <think> and </think> including the tags
        response = re.sub(r'<think>(.*?)</think>', '', response, flags=re.DOTALL)
    
    # Remove leading and trailing whitespace
    response = response.strip()
    
    # Debug: Print the response after processing
    print(f"Processed Response: {response}")
    return response

# Initialize Discord client
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Handle messages
@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    if message.content.startswith('.ask'):
        prompt = message.content[len('.ask '):]
        
        # Load chat history and long-term memory
        chat_history = load_chat_history()
        long_term_memory = load_long_term_memory()
        user_id = str(message.author.id)  # Ensure user_id is a string
        username = message.author.name  # Get the username
        
        # Check if the user is new (not in chat history)
        if user_id not in chat_history:
            # Send the disclaimer message
            await message.channel.send(DISCLAIMER_MESSAGE)
            # Initialize chat history for the new user
            chat_history[user_id] = []
        
        # Get the current user's chat history
        user_chat_history = chat_history.get(user_id, [])
        
        # Combine the current user's chat history into the context
        global_context = user_chat_history[-MAX_HISTORY_MESSAGES:]  # Only use the current user's history
        
        # Check for mentioned users in the prompt
        mentioned_users = []
        for word in prompt.split():
            if word.startswith("<@") and word.endswith(">"):
                mentioned_user_id = extract_user_id_from_mention(word)
                if mentioned_user_id:
                    mentioned_users.append(mentioned_user_id)
        
        # Add long-term memory for the current user and mentioned users
        long_term_context = []
        
        # Prioritize the current user's long-term memory
        if user_id in long_term_memory:
            long_term_context.append(f"Long-Term Memory for {message.author.name}:")
            for key, value in long_term_memory[user_id].items():
                long_term_context.append(f"{key}: {value}")
        
        # Add long-term memory for mentioned users
        for mentioned_user_id in mentioned_users:
            if mentioned_user_id in long_term_memory:
                mentioned_user = await client.fetch_user(mentioned_user_id)
                long_term_context.append(f"Long-Term Memory for {mentioned_user.name}:")
                for key, value in long_term_memory[mentioned_user_id].items():
                    long_term_context.append(f"{key}: {value}")
        
        # Add bot's long-term memory
        if "bot" in long_term_memory:
            long_term_context.append(f"Bot's Long-Term Memory:")
            for key, value in long_term_memory["bot"].items():
                long_term_context.append(f"{key}: {value}")
        
        # Combine long-term memory and chat history into the full context
        full_context = "\n".join(long_term_context) + "\n\n" + "\n".join([f"{msg['role']}: {msg['content']}" for msg in global_context])
        
        # Send a "thinking..." message in the same channel
        thinking_message = await message.channel.send("Thinking...")
        
        # Print the user's message in the terminal
        print(f"\n[User Message] {message.author}: {prompt}")
        
        # Get the response from Ollama API, including global context and long-term memory
        response = ask_ollama(prompt, CHAT_SYSTEM_PROMPT, full_context, long_term_memory)
        
        # Print the Ollama response in the terminal
        print(f"[Ollama Response] {response}")
        
        # Update the current user's chat history with the new interaction
        user_chat_history.append({"role": "User", "content": prompt})
        user_chat_history.append({"role": "Assistant", "content": response})
        
        # Limit the user's chat history to the last MAX_HISTORY_MESSAGES messages
        chat_history[user_id] = user_chat_history[-MAX_HISTORY_MESSAGES:]
        
        # Extract important information from the user's input only
        extracted_infos = extract_important_info(prompt)
        if extracted_infos:
            for important_info in extracted_infos:
                # If no name is specified, associate the information with the current user
                if "name" not in important_info:
                    print("Storing non-user-specific info for the current user:", important_info)
                    target_user_id = user_id  # Use the current user's ID
                    extracted_name = None  # No name is extracted
                else:
                    # Skip if the extracted info is not user-specific
                    if "name" not in important_info:
                        print("Skipping non-user-specific info:", important_info)
                        continue

                    extracted_name = important_info.get("name", "").lower() if important_info.get("name") else None
                    target_user_id = None

                    # Priority 1: Check existing user data for name match
                    if extracted_name:
                        for user_id, user_data in long_term_memory.items():
                            if user_id in ["bot", "name_to_id"]:
                                continue  # Skip bot and name_to_id sections
                            existing_name = user_data.get("name", "").lower()
                            if existing_name == extracted_name:
                                target_user_id = user_id
                                print(f"Found existing user {user_id} with name '{extracted_name}'")
                                break

                    # Priority 2: Use mentioned users if no existing match
                    if not target_user_id:
                        mentioned_users = [extract_user_id_from_mention(word) for word in prompt.split() 
                                        if word.startswith("<@") and word.endswith(">")]
                        if mentioned_users:
                            target_user_id = mentioned_users[0]
                            print(f"Using mentioned user ID: {target_user_id}")

                    # Priority 3: Use name_to_id mapping
                    if not target_user_id and extracted_name:
                        target_user_id = long_term_memory.get("name_to_id", {}).get(extracted_name)
                        if target_user_id:
                            print(f"Using name_to_id mapping: {extracted_name} -> {target_user_id}")

                    # Fallback: Current user's ID
                    if not target_user_id:
                        target_user_id = user_id
                        print(f"Fallback to current user ID: {user_id}")

                    # Update name_to_id mapping if we found a better match
                    if extracted_name and target_user_id:
                        current_mapping = long_term_memory.get("name_to_id", {}).get(extracted_name)
                        if current_mapping != target_user_id:
                            long_term_memory.setdefault("name_to_id", {})[extracted_name] = target_user_id
                            print(f"Updated name_to_id mapping: {extracted_name} -> {target_user_id}")

                # Store information in the identified user's record
                if target_user_id != "name_to_id":  # Ensure we're not storing in the name_to_id section
                    user_entry = long_term_memory.setdefault(target_user_id, {})
                    for key, value in important_info.items():
                        if key != "name":  # Name is handled through the mapping
                            if key in user_entry:
                                # If the key already exists, append the new value
                                if isinstance(user_entry[key], list):
                                    user_entry[key].append(value)  # Append to existing list
                                else:
                                    user_entry[key] = [user_entry[key], value]  # Convert to list and append
                            else:
                                # If the key doesn't exist, create a new entry
                                user_entry[key] = value

                    # Special case: Ensure name is stored in the user's entry
                    if extracted_name and "name" not in user_entry:
                        user_entry["name"] = extracted_name.capitalize()
        
        # Save the updated chat history and long-term memory
        save_chat_history(chat_history)
        save_long_term_memory(long_term_memory)
        
        # Process the <think></think> section
        formatted_response = process_think_section(response)
        
        # Debug print to check response length
        print(f"Response length: {len(formatted_response)}")
        
        # Split the response into chunks of 2000 characters if needed
        if len(formatted_response) > 2000:
            # Split into chunks of 2000 characters
            for i in range(0, len(formatted_response), 2000):
                chunk = formatted_response[i:i+2000]
                await message.channel.send(chunk)
            # Edit the thinking message with a message indicating the response was sent
            await thinking_message.edit(content="Response sent in parts.")
        else:
            # Add a small delay to avoid hitting rate limits
            await asyncio.sleep(1)
            try:
                await thinking_message.edit(content=formatted_response)
            except discord.HTTPException as e:
                print(f"Failed to edit message: {e}")
                await message.channel.send("Failed to update the response message.")
    
    elif message.content.startswith('.clearhistory'):
        user_id = str(message.author.id)  # Ensure user_id is a string
        chat_history = load_chat_history()
        long_term_memory = load_long_term_memory()
        if user_id in chat_history:
            del chat_history[user_id]
            save_chat_history(chat_history)
        if user_id in long_term_memory:
            del long_term_memory[user_id]
            save_long_term_memory(long_term_memory)
        await message.channel.send("Your chat history and long-term memory have been cleared. 🧹")
    elif message.content.startswith('.help'):
        await message.channel.send("**.ask** for chatting with bot\n**.clearhistory** for clearing users history")

# Run the bot
client.run(DISCORD_TOKEN)
