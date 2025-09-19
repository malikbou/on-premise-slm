# Open WebUI User Guide

This guide is for end-users who want to interact with the RAG system through the Open WebUI interface. It assumes the system has already been set up by an administrator.

## A.1 Getting Started

### A.1.1 Accessing Open WebUI

**From Any Device (Desktop, Mobile, Tablet):**

1. **Get the URL from your administrator**
   - The URL will look like: `http://IP_ADDRESS:PORT`
   - Example: `http://90.240.219.112:28244`

2. **Open in your web browser**
   - Works on Chrome, Firefox, Safari, mobile browsers
   - **Mobile users**: Add to home screen for app-like experience

3. **Bookmark the URL** for easy access

### A.1.2 First-Time Setup

1. **Create Your Account**
   - On first visit, you'll see a sign-up form
   - Choose a username and password
   - **Note**: The first user becomes the admin

2. **Admin vs Regular Users**
   - **Admin**: Can configure models and manage users
   - **Regular users**: Can chat with available models

## A.2 Using the Chat Interface

### A.2.1 Selecting Models

You'll see different types of models available:

**🤖 RAG-Enabled Models** (Recommended for handbook questions)
- Names like: `ollama/phi3:mini`, `ollama/phi-4:mini`
- **Best for**: Questions about course information, deadlines, procedures
- **Features**: Retrieves relevant information from handbook documents

**☁️ Cloud Models** (General purpose)
- Names like: `gpt-4o-mini`, `claude-opus`
- **Best for**: General knowledge, coding help, creative tasks
- **Note**: May not have access to local handbook information

### A.2.2 Getting Better Answers

**For Handbook/Course Questions:**
- ✅ Use RAG-enabled models (`ollama/` models)
- ✅ Be specific: "When is the CS dissertation deadline?"
- ✅ Ask follow-up questions for clarification

**Examples of Good Questions:**
