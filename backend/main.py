from fastapi import FastAPI
import asyncio
import random

app = FastAPI(title="Studyflash Support API")

# 1. Il nostro "Database" di email finte
MOCK_EMAILS = [
    {
        "subject": "App crashes on login", 
        "body": "Every time I try to open my flashcards, the app closes. I am using an iPhone 13.", 
        "sender": "angry_user@gmail.com",
        "message_id": "<mock-id-12345>"
    },
    {
        "subject": "Refund please", 
        "body": "I forgot to cancel my trial, can I get my money back?", 
        "sender": "distracted_student@yahoo.com",
        "message_id": "<mock-id-67890>"
    },
    {
        "subject": "How to share decks?", 
        "body": "Hi, how can I send my study deck to my classmate?", 
        "sender": "curious_guy@hotmail.com",
        "message_id": "<mock-id-abcde>"
    }
]

# 2. Il Simulatore (Poller Finto)
async def mock_email_poller():
    print("🚀 Simulatore Email Avviato! In attesa di messaggi...")
    while True:
        # Aspetta 30 secondi (o 10 per fare i test più in fretta)
        await asyncio.sleep(30) 
        
        # Scegli un'email a caso dal nostro finto Outlook
        nuova_email = random.choice(MOCK_EMAILS)
        print(f"\n📩 BZZZ! Nuova email in arrivo da: {nuova_email['sender']}")
        print(f"Oggetto: {nuova_email['subject']}")
        
        # --- QUI INIZIA LA MAGIA ---
        # 1. TRIGGER LANGGRAPH:
        # risultato_ai = tuo_grafo_langgraph.invoke({"testo": nuova_email["body"]})
        print("🧠 LangGraph sta analizzando... (Simulato)")
        
        # 2. SALVATAGGIO NEL DB:
        # salva_ticket_db(nuova_email, risultato_ai)
        print("💾 Ticket salvato nel Database con la bozza AI!")
        # ---------------------------

# 3. Accendi il simulatore quando parte l'app
@app.on_event("startup")
async def startup_event():
    # Fa partire il loop in background senza bloccare le API di FastAPI
    asyncio.create_task(mock_email_poller())

@app.get("/")
def read_root():
    return {"status": "Backend funzionante!"}