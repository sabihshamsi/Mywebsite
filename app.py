from flask import Flask, render_template, redirect, request, jsonify, session
from groq import Groq
from dotenv import load_dotenv
import os
import traceback
import mysql.connector


app = Flask(__name__)
app.secret_key = "super-secret-key"  # needed for 

MAX_ATTEMPTS = 5
VALID_EMAIL = os.getenv("VALID_EMAIL")
VALID_PASSWORD = os.getenv("VALID_PASSWORD")


# Load environment variables
load_dotenv()

# Initialize Groq client
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- DB Helpers ---
def save_login_to_db(role, email, password, status):
    """Save login attempts into DB"""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()
        sql = """
            INSERT INTO conversations (role, email, password, status)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (role, email, password, status))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("DB Insert Error (login):", e)


def save_message_to_db(role, message):
    """Save chatbot messages into DB"""
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        cursor = conn.cursor()
        sql = "INSERT INTO conversations (role, content) VALUES (%s, %s)"
        cursor.execute(sql, (role, message))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("DB Insert Error (chat):", e)


@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")

# Handle login form submission
@app.route("/login", methods=["POST"])
def login():
    email = request.form.get("email", "")
    password = request.form.get("password", "")

    # Initialize attempts if not already
    if "attempts" not in session:
        session["attempts"] = 0

    # If already exceeded max attempts
    if session["attempts"] >= MAX_ATTEMPTS:
        save_login_to_db("Login Blocked", email, password, "Too Many Attempts")
        return render_template("index.html", error="🚫 Too many attempts. Access permanently denied.")

    # ✅ Check if credentials match
    if email == VALID_EMAIL and password == VALID_PASSWORD:
        save_login_to_db("Login Success", email, password, "Access Granted")
        session.pop("attempts", None)  # reset attempts after success
        return redirect("/chatbot")

    # ❌ Wrong credentials
    session["attempts"] += 1
    save_login_to_db("Login Attempt", email, password, "Access Denied")

    if session["attempts"] >= MAX_ATTEMPTS:
        save_login_to_db("Login Blocked", email, password, "Too Many Attempts")
        return render_template("index.html", error="🚫 Too many attempts. Access permanently denied.")

    return render_template("index.html", error="❌ Access Denied. Try again.")

# Show chatbot page
@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_message = request.json.get("message", "")

    try:
        # Save user message
        save_message_to_db("User", user_message)

        completion = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Sabih, in a loving conversation with Wajeeha. "
                        "Reply warmly, affectionately, and playfully in short natural sentences (1–3 max). "
                        "Use sweet emojis like ❤️😘🥰 occasionally. "
                        "Do NOT overuse her name — only mention it once in a while to make it feel special. "
                        "Never break character or mention being AI. "
                        "Always sound like Sabih talking directly to her."
                    )
                },
                {"role": "user", "content": user_message}
            ],
            temperature=0.9,
            max_tokens=120
        )

        bot_reply = completion.choices[0].message.content

        # Save bot reply
        save_message_to_db("Sabih", bot_reply)

        return jsonify({"reply": bot_reply})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

