import os
from openai import OpenAI
from django.conf import settings
from .models import Season, Participation

def get_tournament_context():
    """
    Constructs a context string about the tournament for the AI.
    """
    active_season = Season.objects.filter(is_active=True).first()
    context = "You are the Metro Lanes Open Assistant. Your job is to help users with questions about our bowling tournaments.\n\n"
    
    if active_season:
        context += f"Current Active Season: {active_season.name}\n"
        context += f"Registration Dates: {active_season.register_start_date} to {active_season.register_end_date}\n"
        
        participations = Participation.objects.filter(season=active_season)
        if participations.exists():
            context += "Available Categories and Fees:\n"
            for p in participations:
                context += f"- {p.name} ({p.game_type.name}): KES {p.charge}\n"
    
    context += "\nGeneral Information:\n"
    context += "- Game Mode: Standard 10-Pin Bowling.\n"
    context += "- Venue: Metro Bowl Arena, 452 Commerce Blvd, Industrial District, NY.\n"
    context += "- Contact Email: info@metrolanes.com\n"
    context += "- Tournament Structure: Players/Teams compete in multiple rounds.\n"
    
    context += "\nLead Generation Policy:\n"
    context += "If a user seems interested in joining or has specific questions, politely ask if they'd like to leave their phone number so our team can follow up with more details. Don't be pushy—only ask once or when it feels natural (e.g., 'Would you like us to text you the registration link?'). If they provide a phone number, use the 'save_customer_inquiry' tool immediately.\n"
    
    context += "\nInstructions: Be professional, friendly, and concise. If you don't know something, ask the user to contact us at info@metrolanes.com."
    
    return context

def get_ai_response(messages, user_obj=None):
    """
    messages: List of dicts with 'role' and 'content'
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "I'm sorry, my AI brain is not connected yet (missing API key)."

    client = OpenAI(api_key=api_key)
    system_prompt = get_tournament_context()
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    
    # Define Tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "save_customer_inquiry",
                "description": "Saves a customer's phone number and their question for follow-up.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": {"type": "string", "description": "The user's phone number."},
                        "inquiry": {"type": "string", "description": "The specific question or interest the user expressed."}
                    },
                    "required": ["phone_number", "inquiry"]
                }
            }
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=full_messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=500
        )
        
        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls
        
        if tool_calls:
            # Handle tool calls
            for tool_call in tool_calls:
                if tool_call.function.name == "save_customer_inquiry":
                    import json
                    args = json.loads(tool_call.function.arguments)
                    from .models import CustomerInquiry
                    CustomerInquiry.objects.create(
                        user=user_obj,
                        phone_number=args.get('phone_number'),
                        inquiry_text=args.get('inquiry')
                    )
            
            # Get a final response from AI acknowledging the capture (or just return the response)
            # For simplicity, we'll just add the tool result and get a final reply
            full_messages.append(response_message)
            full_messages.append({
                "tool_call_id": tool_calls[0].id,
                "role": "tool",
                "name": "save_customer_inquiry",
                "content": "Success: Inquiry saved. Inform the user that someone will reach out soon."
            })
            
            second_response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=full_messages
            )
            return second_response.choices[0].message.content

        return response_message.content
    except Exception as e:
        print(f"OpenAI Error: {e}")
        return "I encountered an error while thinking. Please try again in a moment."
