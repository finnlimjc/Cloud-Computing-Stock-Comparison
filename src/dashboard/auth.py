import streamlit as st

from src.storage.storage import DocumentStore

def render_login(store:DocumentStore) -> dict | None:
    """Render log in, sign up and log out controls, returning the signed-in user if there is one."""
    user = st.session_state.get("user")
    if user:
        st.caption(f"Signed in as **{user['username']}**")
        if st.button("Log out", use_container_width=True):
            st.session_state.user = None
            st.rerun()
        return user
    
    login_tab, signup_tab = st.tabs(["Log in", "Sign up"])
    with login_tab:
        with st.form("login_form", border=False):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            user = store.authenticate(username, password)
            if user is None:
                st.error("Invalid username or password.")
            else:
                st.session_state.user = user
                st.rerun()
    
    with signup_tab:
        with st.form("signup_form", border=False):
            username = st.text_input("Username", key="signup_username", help="3 to 32 characters: letters, numbers, - and _.")
            password = st.text_input("Password", type="password", key="signup_password", help="At least 8 characters.")
            confirm = st.text_input("Confirm password", type="password", key="signup_confirm")
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            if password != confirm:
                st.error("The passwords do not match.")
            else:
                try:
                    st.session_state.user = store.register(username, password)
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
    return None
