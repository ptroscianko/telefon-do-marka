import streamlit as st
import google.generativeai as genai
import json
import os

st.set_page_config(page_title="Telefon do Marka", page_icon="📞", layout="wide")
st.title("📞 Telefon do Marka (Trening SPIN)")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    st.error("Brak klucza API. Ustaw GEMINI_API_KEY w ustawieniach zaawansowanych (Secrets).")
    st.stop()

genai.configure(api_key=API_KEY)

system_prompt = """
Jesteś systemem wspierającym trenażer rozmowy sprzedażowej.
Zasady ogólne:
Grasz Marka Kowala (46 lat), właściciela firmy Kowal-Instal: instalacje grzewcze i pompy ciepła, Wrocław. Jesteś obecnym klientem Oferteo. Za 3 tygodnie kończy Ci się pakiet. Dzwoni doradca. Jesteś na budowie, masz mało czasu.
Fakty na start: od wiosny ok. 20 zapytań, odpowiedziałeś na kilka, 2 zlecenia. Zapytania oceniasz jako „średnie”.

Ukryte informacje (ujawniaj TYLKO po kolei i na PASUJĄCE pytanie):
1. Problem (ujawnij na pytanie P): Większość zapytań to drobne naprawy i wyceny "na już", 50-60 km od Wrocławia. Interesują Cię montaże pomp i modernizacje kotłowni.
2. Skutki (ujawnij na pytanie I - po odkryciu problemu): Puste oględziny to pół dnia poza budową. Raz przesunąłeś termin dobremu klientowi i było Ci głupio. Dlatego myślisz nie przedłużać.
3. Czego chcesz (ujawnij na pytanie N - po odkryciu skutków): Przedłużenie ma sens, jeśli będzie mniej zapytań, ale konkretne (pompy, kotłownie) do 40 km od Wrocławia. Jeśli doradca to zaoferuje po etapie 3, okaż zainteresowanie.

Behawior Marka:
- 1-2 krótkie zdania, potocznie.
- Zbywaj pytania zamknięte i zachwalanie oferty przed czasem ("Proszę wysłać maila").
- Nie wymyślaj faktów spoza opisu.

ZAKOŃCZENIE I OCENA:
Jeśli użytkownik wpisze "STOP", wychodzisz z roli Marka i dajesz wyczerpującą ocenę rozmowy doradcy w modelu SPIN:
- Ile pytań było typu S, P, I, N (zacytuj je).
- Jakie ukryte informacje odkryto.
- Czy oferta padła za wcześnie.
- 2 rzeczy dobre, 2 do poprawy, 1 propozycja idealnego pytania.

WAŻNE - WYMÓG TECHNICZNY:
Musisz ZAWSZE i WYŁĄCZNIE odpowiadać prawidłowym formatem JSON bez żadnych dodatkowych znaczników (bez ```json). 
Format JSON:
{
  "odpowiedz": "tutaj tekst odpowiedzi Marka lub treść oceny",
  "etykieta": "S" | "P" | "I" | "N" | "OFERTA" | "INNE",
  "otwartosc": liczba 0-100,
  "etap": liczba 0-3
}
"""

model = genai.GenerativeModel(
    model_name="gemini-3.8-flash",
    system_instruction=system_prompt,
    generation_config={"response_mime_type": "application/json"}
)

from google.api_core.exceptions import ResourceExhausted
import time

if "chat" not in st.session_state:
    st.session_state.chat = model.start_chat(history=[])
    
    try:
        # Dajemy małą przerwę i próbujemy wysłać wiadomość startową
        time.sleep(1)
        st.session_state.chat.send_message("Rozpocznij jako JSON. Czekam na pierwszą wiadomość.")
    except ResourceExhausted:
        st.error("⚠️ Wyczerpano darmowy limit zapytań do Google API (ResourceExhausted). Odczekaj około minuty i odśwież stronę.")
    
    st.session_state.messages = [{"role": "assistant", "content": "Halo, Kowal-Instal, słucham?"}]
    st.session_state.counts = {"S": 0, "P": 0, "I": 0, "N": 0, "OFERTA": 0, "INNE": 0}
    st.session_state.openness = 20
    st.session_state.stage = 0
    st.session_state.last_label = "-"
col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("S (Sytuacja)", st.session_state.counts.get("S", 0))
col2.metric("P (Problem)", st.session_state.counts.get("P", 0))
col3.metric("I (Implikacje)", st.session_state.counts.get("I", 0))
col4.metric("N (Korzyści)", st.session_state.counts.get("N", 0))
col5.metric("Oferta", st.session_state.counts.get("OFERTA", 0))
col6.metric("Ostatni typ", st.session_state.last_label)

st.progress(st.session_state.openness / 100, text=f"Otwartość klienta: {st.session_state.openness}% (Etap: {st.session_state.stage}/3)")
st.divider()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Wpisz swoją kwestię (lub napisz STOP, aby ocenić)...")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("Marek pisze..."):
        try:
            response = st.session_state.chat.send_message(prompt)
            data = json.loads(response.text)
            
            odpowiedz = data.get("odpowiedz", "Błąd parsowania.")
            etykieta = data.get("etykieta", "INNE")
            
            if etykieta in st.session_state.counts:
                st.session_state.counts[etykieta] += 1
            st.session_state.last_label = etykieta
            st.session_state.openness = max(0, min(100, data.get("otwartosc", 20)))
            st.session_state.stage = data.get("etap", 0)

            st.session_state.messages.append({"role": "assistant", "content": odpowiedz})
            st.rerun()
            
        except Exception as e:
            st.error("Błąd połączenia z API. Odśwież stronę.")
