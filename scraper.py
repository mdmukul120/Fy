import asyncio
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from pydantic import BaseModel, Field
from typing import List, Optional

# --- কনফিগারেশন ---
BASE_URL = "https://cfymarkscanjiostar80.top/"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Pydantic Data Models (ডেটা ভ্যালিডেশনের জন্য) ---
class StreamingServer(BaseModel):
    server_name: str
    server_url: str

class MatchData(BaseModel):
    title: str
    match_status: str  # Live, Upcoming, Recent
    image_url: Optional[str] = "No Image"
    time: Optional[str] = "TBA"
    streaming_servers: List[StreamingServer] = Field(default_factory=list)

class TvChannel(BaseModel):
    channel_name: str
    stream_url: str
    logo_url: Optional[str] = ""

class SportsAPI(BaseModel):
    last_updated: str
    matches: List[MatchData]
    tv_channels: List[TvChannel]

# --- ডাইনামিক পেজ ফেচিং (Playwright Deep Dive) ---
async def fetch_dynamic_content(url):
    async with async_playwright() as p:
        # হেডলেস ব্রাউজার চালু করা
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            logging.info(f"Connecting to: {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            # লেজি লোড হওয়া ইমেজ এবং সার্ভার লিংক পেতে পেজ স্ক্রল করা
            logging.info("Scrolling page for deep dive extraction...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(3000) # JS লোড হওয়ার জন্য ৩ সেকেন্ড অপেক্ষা
            
            html_content = await page.content()
            return html_content
            
        except Exception as e:
            logging.error(f"Failed to fetch page: {e}")
            return None
        finally:
            await browser.close()

# --- HTML পার্সিং ---
def parse_html_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    matches_list = []
    tv_channels_list = []

    # ------------------------------------------------------------------
    # সতর্কতা: নিচের সিলেক্টরগুলো (.match-card, .title ইত্যাদি) আপনার 
    # ওয়েবসাইটের আসল HTML ক্লাসের সাথে মিলিয়ে পরিবর্তন করতে হবে।
    # ------------------------------------------------------------------
    
    # ম্যাচ স্ক্র্যাপিং উদাহরণ
    for match_box in soup.select('.match-card-class'): # আসল ক্লাস বসান
        title = match_box.select_one('.match-title').text.strip() if match_box.select_one('.match-title') else "Unknown Match"
        status = match_box.select_one('.badge-status').text.strip() if match_box.select_one('.badge-status') else "Upcoming"
        image = match_box.select_one('img')['src'] if match_box.select_one('img') else ""
        
        # একাধিক সার্ভার লিংক বের করা
        servers = []
        for server_tag in match_box.select('.server-btn'):
            servers.append(StreamingServer(
                server_name=server_tag.text.strip(),
                server_url=server_tag['href']
            ))
            
        matches_list.append(MatchData(
            title=title,
            match_status=status,
            image_url=image,
            streaming_servers=servers
        ))

    # টিভি চ্যানেল স্ক্র্যাপিং উদাহরণ
    for tv_box in soup.select('.tv-channel-class'): # আসল ক্লাস বসান
        ch_name = tv_box.select_one('.ch-name').text.strip() if tv_box.select_one('.ch-name') else "Unknown TV"
        stream_link = tv_box.select_one('a.play')['href'] if tv_box.select_one('a.play') else ""
        
        tv_channels_list.append(TvChannel(
            channel_name=ch_name,
            stream_url=stream_link
        ))

    return matches_list, tv_channels_list

# --- মূল এক্সিকিউশন ---
async def main():
    logging.info("Starting Premium Sports Scraper...")
    html_data = await fetch_dynamic_content(BASE_URL)
    
    if html_data:
        logging.info("HTML fetched successfully. Parsing deep data...")
        matches, channels = parse_html_data(html_data)
        
        # Pydantic মডেলে ডেটা পুশ করা
        final_api_data = SportsAPI(
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            matches=matches,
            tv_channels=channels
        )
        
        # JSON ফাইল সেভ করা
        with open('premium_api.json', 'w', encoding='utf-8') as f:
            f.write(final_api_data.model_dump_json(indent=4))
            
        logging.info("Success! Data saved to premium_api.json")
    else:
        logging.error("Operation aborted due to fetch failure.")

if __name__ == "__main__":
    asyncio.run(main())
