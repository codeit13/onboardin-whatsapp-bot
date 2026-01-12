# Twilio WhatsApp Bot Setup Guide

This guide will help you set up the Twilio WhatsApp bot integration.

## Prerequisites

1. Twilio Account (sign up at https://www.twilio.com)
2. Twilio WhatsApp Sandbox access
3. Public URL for webhook (use ngrok for local development)

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Configure Twilio Credentials

1. Get your Twilio credentials from the Twilio Console:
   - Account SID
   - Auth Token
   - WhatsApp Sandbox number

2. Update your `.env` file:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
TWILIO_WEBHOOK_URL=https://your-domain.com/webhooks/twilio/whatsapp
```

## Step 3: Set Up Local Development (ngrok)

For local development, you need to expose your local server:

```bash
# Install ngrok (if not already installed)
# macOS: brew install ngrok
# Or download from https://ngrok.com

# Start your FastAPI server
python run.py

# In another terminal, start ngrok
ngrok http 8001

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Use this as your TWILIO_WEBHOOK_URL
```

## Step 4: Configure Twilio WhatsApp Sandbox

1. Go to Twilio Console → Messaging → Try it out → Send a WhatsApp message
2. Join the sandbox by sending the join code to the sandbox number
3. Go to WhatsApp Sandbox settings
4. Set the webhook URL to: `https://your-domain.com/webhooks/twilio/whatsapp`
5. Set HTTP method to: `POST`
6. Save the configuration

## Step 5: Test the Integration

1. Send a WhatsApp message to your Twilio sandbox number
2. The webhook will be triggered and your bot will respond
3. Check the logs to see the message processing

## Available Endpoints

### Webhook Endpoint (Twilio calls this)
- **URL**: `/webhooks/twilio/whatsapp`
- **Method**: `POST`
- **Purpose**: Receives incoming WhatsApp messages from Twilio

### Send Message Endpoint (API)
- **URL**: `/webhooks/twilio/whatsapp/send`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "to": "whatsapp:+1234567890",
    "message": "Hello from API!",
    "media_url": "https://example.com/image.jpg" // optional
  }
  ```

## Bot Commands

The bot responds to these commands:

- `start` or `hi` - Begin onboarding process
- `help` or `menu` - Show available options
- `status` - Check onboarding status

## Customization

### Modify Bot Logic

Edit `app/services/whatsapp_service.py` to customize:
- Conversation flow
- State management
- Response messages

### Modify Message Processing

Edit `app/tasks/whatsapp_tasks.py` to customize:
- Message parsing
- Response generation
- Integration with other services

## Production Deployment

1. Use a proper domain (not ngrok)
2. Set up SSL certificate (HTTPS required)
3. Update `TWILIO_WEBHOOK_URL` in production environment
4. Configure proper logging and monitoring
5. Set up Redis for Celery task processing

## Troubleshooting

### Webhook not receiving messages
- Check that your webhook URL is publicly accessible
- Verify the URL in Twilio Console matches your endpoint
- Check server logs for errors
- Ensure HTTPS is used (Twilio requires HTTPS)

### Messages not being processed
- Check Redis is running (for Celery)
- Check Celery worker is running
- Review application logs
- Verify Twilio credentials are correct

### Signature verification failing
- Ensure `TWILIO_AUTH_TOKEN` is set correctly
- Check that the signature header is being passed
- For development, signature verification can be skipped

## Security Notes

1. Always use HTTPS in production
2. Verify Twilio signatures in production
3. Store credentials securely (use environment variables)
4. Implement rate limiting
5. Validate and sanitize all inputs

## Next Steps

- Add database integration for user sessions
- Implement file upload handling
- Add more sophisticated NLP for message understanding
- Integrate with your onboarding system
- Add analytics and monitoring

