import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from threading import Thread
import requests
from bs4 import BeautifulSoup
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, exc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import logging
import sys
import os
from io import StringIO
import queue

# Database configuration
USER = "postgres"
PASSWORD = "choice1914"
HOST = "localhost"
PORT = "5432"
DATABASE_NAME = "scraped_bank_data"
TABLE_NAME = "bank_info"

# Currency conversion rates
EURO_RATE = 0.93
POUND_RATE = 0.80
INR_RATE = 82.95

Base = declarative_base()

# Define the Bank model for the database
class Bank(Base):
    __tablename__ = TABLE_NAME
    id = Column(Integer, primary_key=True)
    rank = Column(Integer)
    bank_name = Column(String)
    market_cap_usd = Column(Float)
    market_cap_eur = Column(Float)
    market_cap_gbp = Column(Float)
    market_cap_inr = Column(Float)

# Function to set up logging
def setup_logger(log_file_path):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(log_file_path, 'w', encoding='utf-8')
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

# Function to scrape data from the website
def scrape_bank_data(url, log_queue):
    try:
        log_queue.put("Scraping data from the website...")
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'class': 'wikitable'})
        if table is None:
            log_queue.put("Error: Could not find the table on the webpage.")
            return None

        table_str = str(table) 
        df = pd.read_html(StringIO(table_str))[0]
        df.rename(columns={'Rank': 'Rank', 'Bank name': 'Bank Name', 'Market cap (US$ billion)': 'Market Cap (US$ billion)'}, inplace=True)
        df = df[['Rank', 'Bank Name', 'Market Cap (US$ billion)']]
        df['Market Cap (US$ billion)'] = pd.to_numeric(df['Market Cap (US$ billion)'], errors='coerce')
        df.dropna(subset=['Market Cap (US$ billion)'], inplace=True)
        log_queue.put("Data scraped successfully.")
        return df
    except requests.exceptions.RequestException as e:
        log_queue.put(f"Error during website request: {e}")
        return None
    except Exception as e:
        log_queue.put(f"An error occurred during scraping: {e}")
        return None

# Function to convert market capitalization to different currencies
def convert_currency(df, log_queue):
    try:
        log_queue.put("Converting currencies...")
        df['Market Cap (EUR billion)'] = df['Market Cap (US$ billion)'] * EURO_RATE
        df['Market Cap (GBP billion)'] = df['Market Cap (US$ billion)'] * POUND_RATE
        df['Market Cap (INR billion)'] = df['Market Cap (US$ billion)'] * INR_RATE
        df['Market Cap (EUR billion)'] = df['Market Cap (EUR billion)'].round(2)
        df['Market Cap (GBP billion)'] = df['Market Cap (GBP billion)'].round(2)
        df['Market Cap (INR billion)'] = df['Market Cap (INR billion)'].round(2)
        log_queue.put("Currency conversion complete.")
        return df
    except KeyError as e:
        log_queue.put(f"Error: Required column not found: {e}")
        return None
    except Exception as e:
        log_queue.put(f"An error occurred during currency conversion: {e}")
        return None

# Function to load data into the database
def load_data_to_db(df, log_queue):
    try:
        log_queue.put("Connecting to the database...")
        DATABASE_URL = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE_NAME}"
        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Check if the table exists and create it if not
        try:
            Base.metadata.create_all(engine)
        except exc.OperationalError:
            log_queue.put("Database table already exists.")

        log_queue.put("Loading data into the database...")
        for _, row in df.iterrows():
            bank = Bank(
                rank=row['Rank'],
                bank_name=row['Bank Name'],
                market_cap_usd=row['Market Cap (US$ billion)'],
                market_cap_eur=row['Market Cap (EUR billion)'],
                market_cap_gbp=row['Market Cap (GBP billion)'],
                market_cap_inr=row['Market Cap (INR billion)']
            )
            session.add(bank)
        session.commit()
        session.close()
        log_queue.put("Data successfully loaded into the database.")
    except exc.SQLAlchemyError as e:
        log_queue.put(f"Error occurred while interacting with the database: {e}")
    except Exception as e:
        log_queue.put(f"An error occurred while loading data to the database: {e}")

# Function to handle the entire process
def process_data(url, log_queue, treeview):
    df = scrape_bank_data(url, log_queue)
    if df is not None:
        df = convert_currency(df, log_queue)
        if df is not None:
            load_data_to_db(df, log_queue)
            display_data_in_gui(df, treeview)
        else:
            log_queue.put("Error: Currency conversion failed. Data not loaded to database.")
    else:
        log_queue.put("Error: Data scraping failed.  Data not loaded to database.")
    log_queue.put("Process completed.")

# Function to display scraped data in the Tkinter Treeview
def display_data_in_gui(df, treeview):
    for row in treeview.get_children():
        treeview.delete(row)

    for index, row in df.iterrows():
        treeview.insert("", "end", values=(
            row['Rank'],
            row['Bank Name'],
            row['Market Cap (US$ billion)'],
            row['Market Cap (EUR billion)'],
            row['Market Cap (GBP billion)'],
            row['Market Cap (INR billion)']
        ))

# Class for the GUI
class DataScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bank Data Scraper")
        self.root.geometry("1000x600")

        self.log_queue = queue.Queue()
        self.logger = setup_logger('scraper_log.txt')

        self.style = ttk.Style()
        self.style.configure('TButton', padding=10, font=('Arial', 12), borderwidth=2, relief="raised")
        self.style.configure('TLabel', font=('Arial', 12))
        self.style.configure('TEntry', font=('Arial', 12))
        self.style.configure('Treeview', font=('Arial', 11), rowheight=30)

        self.url_label = ttk.Label(root, text="URL:")
        self.url_label.pack(pady=(10, 0))
        self.url_entry = ttk.Entry(root, width=80)
        self.url_entry.pack(pady=5)
        self.url_entry.insert(0, "https://web.archive.org/web/20230908091635/https://en.wikipedia.org/wiki/List_of_largest_banks")

        self.data_label = ttk.Label(root, text="Scraped Data:")
        self.data_label.pack(pady=(10, 0))
        self.data_tree = ttk.Treeview(root, columns=("Rank", "Bank Name", "Market Cap (US$ billion)", "Market Cap (EUR billion)", "Market Cap (GBP billion)", "Market Cap (INR billion)"), show="headings", style="Treeview")
        self.data_tree.column("Rank", width=50, anchor="center")
        self.data_tree.column("Bank Name", width=200, anchor="center")
        self.data_tree.column("Market Cap (US$ billion)", width=150, anchor="center")
        self.data_tree.column("Market Cap (EUR billion)", width=150, anchor="center")
        self.data_tree.column("Market Cap (GBP billion)", width=150, anchor="center")
        self.data_tree.column("Market Cap (INR billion)", width=150, anchor="center")
        self.data_tree.heading("Rank", text="Rank")
        self.data_tree.heading("Bank Name", text="Bank Name")
        self.data_tree.heading("Market Cap (US$ billion)", text="Market Cap (US$ billion)")
        self.data_tree.heading("Market Cap (EUR billion)", text="Market Cap (EUR billion)")
        self.data_tree.heading("Market Cap (GBP billion)", text="Market Cap (GBP billion)")
        self.data_tree.heading("Market Cap (INR billion)", text="Market Cap (INR billion)")
        self.data_tree.pack(pady=5, fill=tk.BOTH, expand=True)

        self.tree_scroll = ttk.Scrollbar(root, orient="vertical", command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=self.tree_scroll.set)
        self.tree_scroll.pack(side="right", fill="y")
        self.data_tree.pack(side="left", fill=tk.BOTH, expand=True)

        self.log_label = ttk.Label(root, text="Log:")
        self.log_label.pack(pady=(10, 0))
        self.log_text = scrolledtext.ScrolledText(root, wrap=tk.WORD, width=100, height=10, font=('Arial', 11))
        self.log_text.pack(pady=5, fill=tk.X)

        self.scrape_button = ttk.Button(root, text="Start Scraping", command=self.start_scraping, style='TButton')
        self.scrape_button.pack(pady=10)
        self.quit_button = ttk.Button(root, text="Quit", command=root.destroy, style='TButton')
        self.quit_button.pack(pady=5)

        self.status_label = ttk.Label(root, text="Ready", anchor=tk.W, font=('Arial', 12))
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.log_thread = Thread(target=self.process_log_queue)
        self.log_thread.daemon = True
        self.log_thread.start()

    def start_scraping(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return

        self.scrape_button['state'] = 'disabled'
        self.status_label.config(text="Scraping...")

        # Start scraping process in a separate thread
        scraper_thread = Thread(target=process_data, args=(url, self.log_queue, self.data_tree))
        scraper_thread.daemon = True
        scraper_thread.start()

    def process_log_queue(self):
        while True:
            log_message = self.log_queue.get()
            self.log_text.insert(tk.END, log_message + "\n")
            self.log_text.yview(tk.END)

# Main program
if __name__ == "__main__":
    root = tk.Tk()
    app = DataScraperGUI(root)
    root.mainloop()
