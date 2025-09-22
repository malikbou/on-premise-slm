# Appendix C: User Manual

This guide explains how to use the on-premise RAG system through the OpenWebUI interface.
It assumes that the system has already been set up by an administrator following the System Manual.

---

## A.1 Getting Started

### A.1.1 Accessing the System
1. Your administrator will provide you with:
   - **System URL** (e.g. `http://90.240.219.112:28244`)
   - **Username and password**
2. Open the URL in your web browser (Chrome, Firefox, Safari, or mobile browser).
3. Log in with the credentials you received.

> **Note:** Only the first administrator creates an account directly. All other accounts are added by the admin via **Users → + → Add User**.

---

## A.2 Using the Chat Interface

### A.2.1 Selecting Models
When you open the chat interface, you will see available models.
These names may look long, for example:

- `ollama/hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M`
- `ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M`
- `ollama/hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M`

Your administrator will indicate which models to use.
- **Recommended for handbook queries:** `Falcon3-3B`
- Other models are available for experimentation.

### A.2.2 Suggested Prompts
Your administrator has uploaded a set of **suggested prompts** during setup.
To use them:
1. Click the **Prompt Suggestions** dropdown in the chat bar.
2. Select a prompt (e.g. *“What are the MSc Computer Science term dates?”*).
3. Run it with your chosen model.

This helps you quickly test and explore the system.

---

## A.3 Tips for Better Answers
- **Be specific**: Ask precise questions (e.g. *“What is the deadline for COMP0073 submission?”*).
- **Use context**: If unclear, rephrase the question to include keywords from the handbook.
- **Try different models**: Some may perform better for certain queries.

---

## A.4 Troubleshooting (for Users)

- **Can’t log in?**
  - Check that you are using the correct URL and credentials.
  - Contact your administrator if you need a password reset.

- **Chat feels slow or unresponsive?**
  - Inform your administrator. They may need to restart the model container or check GPU usage.

- **No suggested prompts visible?**
  - Ask your administrator to confirm that the prompt file was uploaded (see System Manual B.5.2).

---

## A.5 Summary
- Log in with credentials from your administrator.
- Select one of the available models.
- Use suggested prompts for quick access to common questions.
- Contact your administrator if you encounter issues.

---
