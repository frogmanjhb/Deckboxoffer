import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time

USD_TO_ZAR = 18  # Conversion rate
STORE_OFFER_PERCENT = 0.4
STORE_CREDIT_PERCENT = 0.5

st.title("Deckbox Collection Value Calculator 🃏💰")
st.write("The app scrapes the entire collection. It shows the total value, the value of cards above 2, the value in rand, and the store offer.")

url = st.text_input("Enter your Deckbox collection URL:")

def debug_show_html(html, tables, rows):
    with st.expander("Debug: Raw HTML and Table Info"):
        st.write(f"Found {len(tables)} tables on the page.")
        if tables:
            st.code(str(tables[0])[:2000], language='html')
        st.write(f"First 3 rows:")
        for row in rows[:3]:
            st.write([c.get_text(strip=True) for c in row.find_all('td')])

@st.cache_data(show_spinner=False)
def get_total_pages(url):
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        page_info = soup.find(string=re.compile(r'Page \\d+ of \\d+'))
        if page_info:
            match = re.search(r'Page \d+ of (\d+)', page_info)
            if match:
                return int(match.group(1))
        last_page = 1
        for a in soup.find_all('a', href=True):
            if '?p=' in a['href']:
                try:
                    page_num = int(a['href'].split('=')[-1])
                    if page_num > last_page:
                        last_page = page_num
                except Exception:
                    continue
        return last_page
    except Exception as e:
        return 1

@st.cache_data(show_spinner=False)
def scrape_deckbox_page(url, debug=False):
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    tables = soup.find_all('table')
    table = None
    for t in tables:
        headers = t.find_all('th')
        if len(headers) >= 5:
            table = t
            break
    data = []
    if not table:
        if debug:
            debug_show_html(soup.prettify(), tables, [])
        return data
    rows = table.find_all('tr')[1:]
    if debug:
        debug_show_html(soup.prettify(), tables, rows)
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 5:
            continue
        qty = cols[0].get_text(strip=True)
        name = cols[1].get_text(strip=True)
        price_text = cols[3].get_text(strip=True)
        price_match = re.search(r'\$(\d+\.\d+)', price_text)
        price = float(price_match.group(1)) if price_match else 0.0
        try:
            qty = int(qty)
        except Exception:
            qty = 1
        data.append({
            'Name': name,
            'Quantity': qty,
            'Price': price,
            'Total': qty * price
        })
    return data

def scrape_entire_collection(base_url):
    base_url = re.sub(r'\?p=\d+$', '', base_url)
    total_pages = get_total_pages(base_url)
    all_cards = []
    progress = st.progress(0, text="Scraping Deckbox pages...")
    for page in range(1, total_pages + 1):
        if page == 1:
            page_url = base_url
        else:
            page_url = f"{base_url}?p={page}"
        try:
            cards = scrape_deckbox_page(page_url, debug=(page==1))
            all_cards.extend(cards)
        except Exception as e:
            st.warning(f"Failed to scrape page {page}: {e}")
        progress.progress(page / total_pages, text=f"Scraping page {page} of {total_pages}")
        time.sleep(0.2)
    progress.empty()
    return all_cards

def aggregate_cards(cards):
    df = pd.DataFrame(cards)
    if df.empty:
        return df, 0.0
    grouped = df.groupby(['Name', 'Price'], as_index=False).agg({'Quantity': 'sum', 'Total': 'sum'})
    total_value = grouped['Total'].sum()
    grouped = grouped.sort_values(by='Total', ascending=False)
    return grouped, total_value

if url:
    with st.spinner("Scraping your entire Deckbox collection..."):
        try:
            cards = scrape_entire_collection(url)
            df_all, total_value_all = aggregate_cards(cards)
            # Filter for cards $2+
            cards_2plus = [c for c in cards if c['Price'] >= 2.0]
            df_2plus, total_value_2plus = aggregate_cards(cards_2plus)
            # Rand values
            total_value_all_rand = total_value_all * USD_TO_ZAR
            total_value_2plus_rand = total_value_2plus * USD_TO_ZAR
            store_offer_usd = total_value_2plus * STORE_OFFER_PERCENT
            store_offer_rand = store_offer_usd * USD_TO_ZAR
            store_credit_usd = total_value_2plus * STORE_CREDIT_PERCENT
            store_credit_rand = store_credit_usd * USD_TO_ZAR
            st.header(":moneybag: Collection Summary")
            st.write(f"Total collection worth: {total_value_all:,.2f}  |  R{total_value_all_rand:,.2f}")
            st.write(f"Cards 2 and up worth: {total_value_2plus:,.2f}  |  R{total_value_2plus_rand:,.2f}")
            st.write(f"Store offer (forty percent of 2 and up): {store_offer_usd:,.2f}  |  R{store_offer_rand:,.2f}")
            st.write(f"Store credit (fifty percent of 2 and up): {store_credit_usd:,.2f}  |  R{store_credit_rand:,.2f}")
            st.write("---")
            st.subheader("All Cards")
            if not df_all.empty:
                st.dataframe(df_all, use_container_width=True)
            else:
                st.warning("No cards found. Please check your collection URL.")
            st.subheader("Cards 2 and Up (Store Offer Table)")
            if not df_2plus.empty:
                st.dataframe(df_2plus, use_container_width=True)
            else:
                st.warning("No cards 2 or greater found.")
        except Exception as e:
            st.error(f"Error: {e}") 