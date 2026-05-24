import uuid
import streamlit as st
import httpx

API_BASE = "http://localhost:8000"

# === Session state init ===
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []


# === API helpers ===
def api_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_request(method, path, **kwargs):
    url = f"{API_BASE}{path}"
    headers = api_headers()
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    with httpx.Client(timeout=120) as client:
        return client.request(method, url, headers=headers, **kwargs)


# === Auth ===
def login_page():
    st.title("EnterpriseRAG — Login")
    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                resp = api_request("POST", "/api/auth/login", json={"username": username, "password": password})
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["access_token"]
                    user_resp = api_request("GET", "/api/auth/me")
                    st.session_state.user = user_resp.json()
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "Login failed"))

    with tab2:
        with st.form("register"):
            reg_user = st.text_input("Choose username")
            reg_pass = st.text_input("Choose password", type="password")
            if st.form_submit_button("Register"):
                resp = api_request("POST", "/api/auth/register", json={"username": reg_user, "password": reg_pass})
                if resp.status_code == 201:
                    st.success("Registered! Please login.")
                else:
                    st.error(resp.json().get("detail", "Registration failed"))


# === Document Management ===
def document_management():
    st.sidebar.subheader("📄 Documents")
    resp = api_request("GET", "/api/documents")
    if resp.status_code == 200:
        docs = resp.json()
        for doc in docs:
            col1, col2 = st.sidebar.columns([3, 1])
            col1.text(f"{doc['filename']} ({doc['status']})")
            if col2.button("🗑", key=doc["id"]):
                api_request("DELETE", f"/api/documents/{doc['id']}")
                st.rerun()

    uploaded = st.sidebar.file_uploader("Upload document", type=["pdf", "md", "txt", "docx"])
    if uploaded:
        files = {"file": (uploaded.name, uploaded.read(), uploaded.type)}
        resp = api_request("POST", "/api/documents/upload", files=files)
        if resp.status_code == 201:
            st.sidebar.success(f"Uploaded: {uploaded.name}")
            st.rerun()
        else:
            st.sidebar.error(resp.json().get("detail", "Upload failed"))


# === Conversation ===
def conversation_sidebar():
    st.sidebar.subheader("💬 Conversations")
    resp = api_request("GET", "/api/conversations")
    if resp.status_code == 200:
        convs = resp.json()
        for conv in convs:
            if st.sidebar.button(conv["title"][:30], key=conv["id"]):
                st.session_state.conversation_id = conv["id"]
                msg_resp = api_request("GET", f"/api/conversations/{conv['id']}")
                if msg_resp.status_code == 200:
                    st.session_state.messages = [
                        {"role": m["role"], "content": m["content"]}
                        for m in msg_resp.json()
                    ]
                st.rerun()

        if st.sidebar.button("New conversation"):
            st.session_state.conversation_id = None
            st.session_state.messages = []
            st.rerun()


# === Chat ===
def chat_interface():
    st.title("EnterpriseRAG")
    st.caption("Ask questions about your documents. Answers include source citations.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask a question..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Searching documents..."):
                resp = api_request("POST", "/api/qa/ask", json={
                    "question": prompt,
                    "conversation_id": st.session_state.conversation_id,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["answer"]
                    sources = data["sources"]
                    st.session_state.conversation_id = data["conversation_id"]

                    st.markdown(answer)

                    if sources:
                        with st.expander("Sources"):
                            for s in sources:
                                st.write(f"**{s['filename']}** (score: {s['score']:.4f})")
                                st.caption(s["chunk_text"][:300] + "...")
                                st.divider()

                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    err = resp.json().get("detail", "Unknown error")
                    st.error(f"Error: {err}")
                    st.session_state.messages.pop()


# === Main ===
def main():
    if not st.session_state.token:
        login_page()
        return

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())

    document_management()
    conversation_sidebar()
    chat_interface()


if __name__ == "__main__":
    main()
