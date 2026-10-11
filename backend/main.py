import asyncio
import json
import os
import math
import re
import time
from collections import Counter
import requests
from pydantic import BaseModel
from datetime import datetime, timezone
from dark_fleet import flag_dark_ships
from contextlib import asynccontextmanager

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
API_KEY = os.getenv("AISSTREAM_API_KEY")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"


PORTS: list[dict] = []

def fetch_ports():
    global PORTS
    try:
        resp = requests.get(
            "https://services2.arcgis.com/jUpNdisbWqRpMo35/ArcGIS/rest/services/WPI_Ports2017/FeatureServer/0/query",
            params={
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "f": "geojson",
                "resultRecordCount": 4000,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        loaded = []
        for f in data.get("features", []):
            geom = f.get("geometry")
            if not geom or not geom.get("coordinates"):
                continue
            props = f.get("properties", {})
            name = (
                props.get("PORT_NAME") or props.get("PORTNAME") or
                props.get("NAME") or props.get("Name") or props.get("name") or "Unknown Port"
            )
            lng, lat = geom["coordinates"]
            loaded.append({"name": name, "lat": lat, "lng": lng})
        PORTS = loaded
        print(f"Loaded {len(PORTS)} ports from World Port Index")
    except Exception as e:
        print(f"Failed to load World Port Index: {e}")


# Trimmed copies of the frontend's curated facility lists — name/coordinates/type
# only, just enough for the chat assistant to look one up and point to it on the
# globe. Full descriptions (country, note) live only in the frontend, shown when
# a marker is clicked directly.
FACILITIES = [
    # Lighthouses
    {"name": "Tower of Hercules", "lat": 43.3853, "lng": -8.4066, "kind": "lighthouse"},
    {"name": "Portland Head Light", "lat": 43.6231, "lng": -70.2083, "kind": "lighthouse"},
    {"name": "Lighthouse of Chania", "lat": 35.5138, "lng": 24.0203, "kind": "lighthouse"},
    {"name": "Fanad Lighthouse", "lat": 55.2764, "lng": -7.6378, "kind": "lighthouse"},
    {"name": "Les Eclaireurs Lighthouse", "lat": -54.8730, "lng": -67.6800, "kind": "lighthouse"},
    {"name": "Peggy's Cove Lighthouse", "lat": 44.4918, "lng": -63.9155, "kind": "lighthouse"},
    {"name": "Lindau Lighthouse", "lat": 47.5460, "lng": 9.6840, "kind": "lighthouse"},
    {"name": "Tourlitis Lighthouse", "lat": 37.6350, "lng": 24.9500, "kind": "lighthouse"},
    {"name": "Pigeon Point Lighthouse", "lat": 37.1789, "lng": -122.3944, "kind": "lighthouse"},
    {"name": "Cape Hatteras Lighthouse", "lat": 35.2508, "lng": -75.5292, "kind": "lighthouse"},
    {"name": "Heceta Head Light", "lat": 44.1377, "lng": -124.1276, "kind": "lighthouse"},
    {"name": "Formentor Lighthouse", "lat": 39.9583, "lng": 3.2075, "kind": "lighthouse"},
    {"name": "Lindesnes Lighthouse", "lat": 57.9838, "lng": 7.0453, "kind": "lighthouse"},
    {"name": "Split Rock Lighthouse", "lat": 47.2001, "lng": -91.3675, "kind": "lighthouse"},
    {"name": "Cape Byron Light", "lat": -28.6382, "lng": 153.6382, "kind": "lighthouse"},
    {"name": "Diamond Head Lighthouse", "lat": 21.2559, "lng": -157.8064, "kind": "lighthouse"},
    {"name": "Kõpu Lighthouse", "lat": 58.9167, "lng": 22.1000, "kind": "lighthouse"},
    {"name": "Eldred Rock Light", "lat": 58.9833, "lng": -135.2167, "kind": "lighthouse"},
    {"name": "Hook Lighthouse", "lat": 52.1242, "lng": -6.9297, "kind": "lighthouse"},
    {"name": "Fastnet Rock Lighthouse", "lat": 51.3856, "lng": -9.6033, "kind": "lighthouse"},
    {"name": "Maiden's Tower Lighthouse", "lat": 41.0211, "lng": 29.0044, "kind": "lighthouse"},
    {"name": "Bodie Island Lighthouse", "lat": 35.8228, "lng": -75.5647, "kind": "lighthouse"},
    {"name": "Felgueiras Lighthouse", "lat": 41.1500, "lng": -8.6700, "kind": "lighthouse"},
    {"name": "Bell Rock Lighthouse", "lat": 56.4331, "lng": -2.3831, "kind": "lighthouse"},
    {"name": "South Stack Lighthouse", "lat": 53.3086, "lng": -4.6967, "kind": "lighthouse"},
    {"name": "Jeddah Light", "lat": 21.4858, "lng": 39.1500, "kind": "lighthouse"},
    {"name": "Low Lighthouse", "lat": 51.2378, "lng": -3.0044, "kind": "lighthouse"},
    {"name": "Makapu'u Point Light", "lat": 21.3106, "lng": -157.6494, "kind": "lighthouse"},
    {"name": "Cape Point Lighthouse", "lat": -34.3568, "lng": 18.4970, "kind": "lighthouse"},
    {"name": "Mouro Island Lighthouse", "lat": 43.4644, "lng": -3.7728, "kind": "lighthouse"},
    {"name": "Point Bonita Lighthouse", "lat": 37.8158, "lng": -122.5328, "kind": "lighthouse"},
    {"name": "St. Joseph Lighthouse", "lat": 42.1119, "lng": -86.4956, "kind": "lighthouse"},
    {"name": "Cape Reinga Lighthouse", "lat": -34.4269, "lng": 172.6817, "kind": "lighthouse"},
    {"name": "Sambro Island Light", "lat": 44.4611, "lng": -63.5975, "kind": "lighthouse"},
    {"name": "Rubjerg Knude Lighthouse", "lat": 57.4489, "lng": 9.7856, "kind": "lighthouse"},
    {"name": "Gay Head Light", "lat": 41.3489, "lng": -70.8347, "kind": "lighthouse"},
    {"name": "Créac'h Lighthouse", "lat": 48.4578, "lng": -5.1247, "kind": "lighthouse"},
    {"name": "Start Point Lighthouse", "lat": 50.2211, "lng": -3.6386, "kind": "lighthouse"},
    {"name": "Whiteford Lighthouse", "lat": 51.5883, "lng": -4.2453, "kind": "lighthouse"},
    {"name": "Point Vicente Lighthouse", "lat": 33.7444, "lng": -118.4128, "kind": "lighthouse"},
    {"name": "Rockland Harbor Breakwater Light", "lat": 44.1114, "lng": -69.0783, "kind": "lighthouse"},
    {"name": "Beachy Head Lighthouse", "lat": 50.7386, "lng": 0.2447, "kind": "lighthouse"},
    {"name": "Hog (Paradise) Island Lighthouse", "lat": 25.0850, "lng": -77.3050, "kind": "lighthouse"},
    {"name": "Pemaquid Point Light", "lat": 43.8372, "lng": -69.5058, "kind": "lighthouse"},
    {"name": "St. Augustine Light", "lat": 29.8850, "lng": -81.2878, "kind": "lighthouse"},
    {"name": "St. Mary's Lighthouse", "lat": 55.0722, "lng": -1.4472, "kind": "lighthouse"},
    {"name": "Neist Point Lighthouse", "lat": 57.4256, "lng": -6.7883, "kind": "lighthouse"},
    {"name": "La Corbière Lighthouse", "lat": 49.1867, "lng": -2.2306, "kind": "lighthouse"},
    {"name": "Kjeungskjær Lighthouse", "lat": 63.7594, "lng": 9.9944, "kind": "lighthouse"},
    {"name": "Lighthouse of Genoa", "lat": 44.4105, "lng": 8.9114, "kind": "lighthouse"},
    {"name": "Cape Neddick Light", "lat": 43.1656, "lng": -70.5928, "kind": "lighthouse"},
    {"name": "Galle Lighthouse", "lat": 6.0261, "lng": 80.2172, "kind": "lighthouse"},
    {"name": "Middle Bay Light", "lat": 30.3958, "lng": -88.0192, "kind": "lighthouse"},
    {"name": "Slettnes Lighthouse", "lat": 71.0972, "lng": 28.2158, "kind": "lighthouse"},
    {"name": "Hornby Lighthouse", "lat": -33.8306, "lng": 151.2789, "kind": "lighthouse"},
    {"name": "Yaquina Head Light", "lat": 44.6799, "lng": -124.0794, "kind": "lighthouse"},
    {"name": "Enoshima Sea Candle", "lat": 35.2997, "lng": 139.4800, "kind": "lighthouse"},
    {"name": "Vizhinjam Lighthouse", "lat": 8.3789, "lng": 76.9711, "kind": "lighthouse"},
    {"name": "Nugget Point Lighthouse", "lat": -46.4467, "lng": 169.8189, "kind": "lighthouse"},
    {"name": "Cape Leeuwin Lighthouse", "lat": -34.3739, "lng": 115.1358, "kind": "lighthouse"},
    {"name": "Eastern Point Light", "lat": 42.5772, "lng": -70.6636, "kind": "lighthouse"},
    {"name": "Green Point Lighthouse", "lat": -33.9033, "lng": 18.4008, "kind": "lighthouse"},
    {"name": "Koh Lanta Lighthouse", "lat": 7.5000, "lng": 99.0500, "kind": "lighthouse"},
    {"name": "Kołobrzeg Lighthouse", "lat": 54.1811, "lng": 15.5622, "kind": "lighthouse"},
    {"name": "Los Morrillos Lighthouse", "lat": 17.9333, "lng": -67.1936, "kind": "lighthouse"},
    {"name": "Nazaré Lighthouse", "lat": 39.6011, "lng": -9.0808, "kind": "lighthouse"},
    {"name": "Yokohama Marine Tower", "lat": 35.4425, "lng": 139.6503, "kind": "lighthouse"},
    {"name": "Cape Espichel Lighthouse", "lat": 38.4167, "lng": -9.2167, "kind": "lighthouse"},
    {"name": "Kermorvan Lighthouse", "lat": 48.3600, "lng": -4.7900, "kind": "lighthouse"},
    {"name": "Gibbs Hill Lighthouse", "lat": 32.2489, "lng": -64.8383, "kind": "lighthouse"},
    {"name": "Cape Palliser Lighthouse", "lat": -41.6108, "lng": 175.2839, "kind": "lighthouse"},
    {"name": "Big Sable Point Light", "lat": 44.0561, "lng": -86.5122, "kind": "lighthouse"},
    {"name": "Jose Ignacio Lighthouse", "lat": -34.8386, "lng": -54.6667, "kind": "lighthouse"},
    {"name": "Punta Penna Lighthouse", "lat": 42.1611, "lng": 14.7508, "kind": "lighthouse"},
    {"name": "Cape Agulhas Lighthouse", "lat": -34.8286, "lng": 20.0122, "kind": "lighthouse"},
    {"name": "Fingal Head Light", "lat": -28.2064, "lng": 153.5647, "kind": "lighthouse"},
    {"name": "Fox Point Lighthouse", "lat": 51.3717, "lng": -55.5808, "kind": "lighthouse"},
    {"name": "Hillsboro Inlet Light", "lat": 26.2589, "lng": -80.0806, "kind": "lighthouse"},
    {"name": "La Jument Lighthouse", "lat": 48.2489, "lng": -5.1319, "kind": "lighthouse"},
    {"name": "Portland Bill Lighthouse", "lat": 50.5164, "lng": -2.4581, "kind": "lighthouse"},
    {"name": "Sumiyoshi Lighthouse", "lat": 34.6136, "lng": 135.4939, "kind": "lighthouse"},
    {"name": "Punta del Hidalgo Lighthouse", "lat": 28.5672, "lng": -16.3236, "kind": "lighthouse"},
    {"name": "Point Reyes Lighthouse", "lat": 37.9950, "lng": -123.0181, "kind": "lighthouse"},
    {"name": "Alcatraz Island Lighthouse", "lat": 37.8267, "lng": -122.4230, "kind": "lighthouse"},
    {"name": "Cape Horn Lighthouse", "lat": -55.9789, "lng": -67.2919, "kind": "lighthouse"},
    {"name": "San Juan del Salvamento Lighthouse", "lat": -54.7397, "lng": -63.8067, "kind": "lighthouse"},
    {"name": "Tillamook Rock Light", "lat": 45.9375, "lng": -124.0161, "kind": "lighthouse"},
    {"name": "Tranøy Lighthouse", "lat": 68.4394, "lng": 15.9497, "kind": "lighthouse"},
    {"name": "Al Ayjah Lighthouse", "lat": 22.5667, "lng": 59.5333, "kind": "lighthouse"},
    {"name": "Amédée Lighthouse", "lat": -22.4839, "lng": 166.4728, "kind": "lighthouse"},
    {"name": "Baishamen Lighthouse", "lat": 20.0500, "lng": 110.3833, "kind": "lighthouse"},
    {"name": "Ribadeo Lighthouse", "lat": 43.5611, "lng": -7.0322, "kind": "lighthouse"},
    {"name": "Knarrarós Lighthouse", "lat": 63.8631, "lng": -21.1150, "kind": "lighthouse"},
    {"name": "Kullen Lighthouse", "lat": 56.3011, "lng": 12.4553, "kind": "lighthouse"},
    {"name": "South Haven Light", "lat": 42.4028, "lng": -86.2833, "kind": "lighthouse"},
    {"name": "White Shoal Light", "lat": 45.8394, "lng": -85.1417, "kind": "lighthouse"},
    {"name": "Cikoneng Lighthouse", "lat": -6.8447, "lng": 105.2011, "kind": "lighthouse"},
    {"name": "Farallon Island Light", "lat": 37.6975, "lng": -123.0011, "kind": "lighthouse"},
    {"name": "Holland Harbor Light", "lat": 42.7742, "lng": -86.2144, "kind": "lighthouse"},
    {"name": "Izumo Hinomisaki Lighthouse", "lat": 35.4381, "lng": 132.6167, "kind": "lighthouse"},
    {"name": "Kiipsaare Lighthouse", "lat": 58.5333, "lng": 21.8333, "kind": "lighthouse"},
    {"name": "Point Sur Lighthouse", "lat": 36.3081, "lng": -121.9042, "kind": "lighthouse"},
    {"name": "Promthep Cape Lighthouse", "lat": 7.7644, "lng": 98.3033, "kind": "lighthouse"},
    {"name": "Cape Spear Lighthouse", "lat": 47.5225, "lng": -52.6197, "kind": "lighthouse"},
    {"name": "Earhart Light", "lat": 0.8081, "lng": -176.6178, "kind": "lighthouse"},
    {"name": "Eddystone Lighthouse", "lat": 50.1811, "lng": -4.1592, "kind": "lighthouse"},
    {"name": "Isla Mujeres Lighthouse", "lat": 21.2314, "lng": -86.7286, "kind": "lighthouse"},
    {"name": "Lismore Lighthouse", "lat": 56.4292, "lng": -5.5992, "kind": "lighthouse"},
    {"name": "Montauk Point Light", "lat": 41.0717, "lng": -71.8567, "kind": "lighthouse"},
    {"name": "Royal Sovereign Lighthouse", "lat": 50.7139, "lng": 0.4353, "kind": "lighthouse"},
    {"name": "Santa Marta Lighthouse", "lat": 38.6975, "lng": -9.4211, "kind": "lighthouse"},
    {"name": "Thomas Point Shoal Light", "lat": 38.8994, "lng": -76.4364, "kind": "lighthouse"},
    {"name": "Toledo Harbor Light", "lat": 41.7469, "lng": -83.3339, "kind": "lighthouse"},
    {"name": "Cape Race Lighthouse", "lat": 46.6600, "lng": -53.0761, "kind": "lighthouse"},
    {"name": "Castle Hill Light", "lat": 41.4589, "lng": -71.3608, "kind": "lighthouse"},
    {"name": "Macquarie Lighthouse", "lat": -33.8236, "lng": 151.2856, "kind": "lighthouse"},
    {"name": "Petit Minou Lighthouse", "lat": 48.3597, "lng": -4.6197, "kind": "lighthouse"},
    {"name": "Sergipe Light", "lat": -10.9111, "lng": -37.0500, "kind": "lighthouse"},
    {"name": "Sandy Hook Light", "lat": 40.4611, "lng": -73.9928, "kind": "lighthouse"},
    {"name": "Battery Point Light", "lat": 41.7461, "lng": -124.2100, "kind": "lighthouse"},
    {"name": "Cape du Couedic Lighthouse", "lat": -36.0667, "lng": 136.7000, "kind": "lighthouse"},
    {"name": "Green Cape Lighthouse", "lat": -37.2647, "lng": 149.9683, "kind": "lighthouse"},
    {"name": "Húsavík Light", "lat": 66.0449, "lng": -17.3389, "kind": "lighthouse"},
    {"name": "Madang Lighthouse", "lat": -5.2214, "lng": 145.7947, "kind": "lighthouse"},
    {"name": "Oak Island Light", "lat": 33.8847, "lng": -78.0181, "kind": "lighthouse"},
    {"name": "Point Pinos Lighthouse", "lat": 36.6350, "lng": -121.9339, "kind": "lighthouse"},
    {"name": "Point Prim Lighthouse", "lat": 46.0561, "lng": -63.0758, "kind": "lighthouse"},
    {"name": "Cape Egmont Lighthouse", "lat": -39.2967, "lng": 173.9450, "kind": "lighthouse"},
    {"name": "Cape Guardafui Lighthouse", "lat": 11.8167, "lng": 51.2833, "kind": "lighthouse"},
    {"name": "Hope Town Lighthouse", "lat": 26.5386, "lng": -76.9814, "kind": "lighthouse"},
    {"name": "Marjaniemi Lighthouse", "lat": 65.0403, "lng": 24.5561, "kind": "lighthouse"},
    {"name": "Marshall Point Light", "lat": 43.9219, "lng": -69.2597, "kind": "lighthouse"},
    {"name": "Smeaton's Tower", "lat": 50.3644, "lng": -4.1408, "kind": "lighthouse"},
    {"name": "Bass Harbor Head Light", "lat": 44.2233, "lng": -68.3372, "kind": "lighthouse"},
    {"name": "Enragée Point Lighthouse", "lat": 45.6167, "lng": -60.9833, "kind": "lighthouse"},
    {"name": "Île Vierge Lighthouse", "lat": 48.6042, "lng": -4.5636, "kind": "lighthouse"},
    {"name": "Key West Lighthouse", "lat": 24.5514, "lng": -81.8014, "kind": "lighthouse"},
    {"name": "West Point Light", "lat": 47.6631, "lng": -122.4283, "kind": "lighthouse"},
    {"name": "Wind Point Light", "lat": 42.7847, "lng": -87.7789, "kind": "lighthouse"},
    {"name": "Burlington Breakwater Lights", "lat": 44.4761, "lng": -73.2264, "kind": "lighthouse"},
    {"name": "California Lighthouse", "lat": 12.6208, "lng": -70.0428, "kind": "lighthouse"},
    {"name": "Cape Henry Lighthouse", "lat": 36.9256, "lng": -76.0058, "kind": "lighthouse"},
    {"name": "Castle Point Lighthouse", "lat": -40.9014, "lng": 176.2192, "kind": "lighthouse"},
    {"name": "Notre-Dame-des-Anges Lighthouse", "lat": 42.5256, "lng": 3.0836, "kind": "lighthouse"},
    {"name": "Klein Curaçao Lighthouse", "lat": 11.9906, "lng": -68.6608, "kind": "lighthouse"},
    {"name": "Porer Lighthouse", "lat": 44.7503, "lng": 13.8867, "kind": "lighthouse"},
    {"name": "Slangkop Lighthouse", "lat": -34.1394, "lng": 18.3242, "kind": "lighthouse"},
    {"name": "Louisbourg Lighthouse", "lat": 45.9106, "lng": -59.9636, "kind": "lighthouse"},
    {"name": "Cabo de Palos Lighthouse", "lat": 37.6386, "lng": -0.6997, "kind": "lighthouse"},
    {"name": "Cape Finisterre Lighthouse", "lat": 42.8781, "lng": -9.2714, "kind": "lighthouse"},

    # Ship recycling yards
    {"name": "Alang Ship Breaking Yard", "lat": 21.42, "lng": 72.13, "kind": "recycling"},
    {"name": "Chittagong Ship Breaking Yard", "lat": 22.30, "lng": 91.75, "kind": "recycling"},
    {"name": "Gadani Ship Breaking Yard", "lat": 25.10, "lng": 66.73, "kind": "recycling"},
    {"name": "Aliağa Ship Recycling", "lat": 38.80, "lng": 26.97, "kind": "recycling"},
    {"name": "Zhangjiagang Ship Recycling", "lat": 31.87, "lng": 120.56, "kind": "recycling"},
    {"name": "Brownsville Ship Channel", "lat": 25.95, "lng": -97.35, "kind": "recycling"},
    {"name": "Galloo Ship Recycling – Ghent", "lat": 51.09, "lng": 3.72, "kind": "recycling"},
    {"name": "Able UK – Teesside", "lat": 54.60, "lng": -1.15, "kind": "recycling"},
    {"name": "Green Yard – Kleven", "lat": 62.47, "lng": 6.02, "kind": "recycling"},
    {"name": "Rotterdam Green Ship Recycling", "lat": 51.90, "lng": 4.48, "kind": "recycling"},
    {"name": "Leyal Ship Recycling – Aliağa", "lat": 38.79, "lng": 26.98, "kind": "recycling"},
    {"name": "Kaohsiung Ship Recycling", "lat": 22.58, "lng": 120.28, "kind": "recycling"},
    {"name": "Mumbai Ship Breaking (Darukhana)", "lat": 18.96, "lng": 72.85, "kind": "recycling"},
    {"name": "Jiangyin Ship Recycling", "lat": 31.91, "lng": 120.28, "kind": "recycling"},
    {"name": "Avilés Ship Recycling", "lat": 43.57, "lng": -5.92, "kind": "recycling"},

    # Bunkering stations
    {"name": "Port of Singapore Bunkering Hub", "lat": 1.26, "lng": 103.82, "kind": "bunker"},
    {"name": "Fujairah Bunkering Anchorage", "lat": 25.12, "lng": 56.34, "kind": "bunker"},
    {"name": "Rotterdam Bunkering Hub", "lat": 51.95, "lng": 4.14, "kind": "bunker"},
    {"name": "Zhoushan Bunkering Hub", "lat": 29.98, "lng": 122.21, "kind": "bunker"},
    {"name": "Hong Kong Bunkering Hub", "lat": 22.28, "lng": 114.16, "kind": "bunker"},
    {"name": "Antwerp Bunkering Hub", "lat": 51.29, "lng": 4.34, "kind": "bunker"},
    {"name": "Busan Bunkering Hub", "lat": 35.10, "lng": 129.04, "kind": "bunker"},
    {"name": "Gibraltar Bunkering Anchorage", "lat": 36.14, "lng": -5.35, "kind": "bunker"},
    {"name": "Panama Canal Bunkering (Balboa/Cristóbal)", "lat": 8.95, "lng": -79.55, "kind": "bunker"},
    {"name": "Algeciras Bunkering Hub", "lat": 36.14, "lng": -5.45, "kind": "bunker"},
    {"name": "Los Angeles/Long Beach Bunkering", "lat": 33.74, "lng": -118.26, "kind": "bunker"},
    {"name": "Shanghai Bunkering Hub", "lat": 31.23, "lng": 121.47, "kind": "bunker"},
    {"name": "Piraeus Bunkering Hub", "lat": 37.94, "lng": 23.65, "kind": "bunker"},
    {"name": "Port Said Bunkering", "lat": 31.26, "lng": 32.30, "kind": "bunker"},
    {"name": "Tanjung Pelepas Bunkering", "lat": 1.36, "lng": 103.55, "kind": "bunker"},
    {"name": "Houston Bunkering Hub", "lat": 29.73, "lng": -95.02, "kind": "bunker"},
    {"name": "Colombo Bunkering Hub", "lat": 6.95, "lng": 79.84, "kind": "bunker"},
    {"name": "Yokohama Bunkering Hub", "lat": 35.44, "lng": 139.64, "kind": "bunker"},
    {"name": "Ulsan Bunkering Hub", "lat": 35.50, "lng": 129.38, "kind": "bunker"},
    {"name": "New York/New Jersey Bunkering", "lat": 40.68, "lng": -74.03, "kind": "bunker"},
    {"name": "Durban Bunkering Hub", "lat": -29.87, "lng": 31.02, "kind": "bunker"},
    {"name": "Las Palmas Bunkering Hub", "lat": 28.15, "lng": -15.41, "kind": "bunker"},
    {"name": "Ningbo-Zhoushan Bunkering", "lat": 29.87, "lng": 121.55, "kind": "bunker"},
    {"name": "Jebel Ali Bunkering Hub", "lat": 25.01, "lng": 55.06, "kind": "bunker"},
    {"name": "Constanța Bunkering Hub", "lat": 44.16, "lng": 28.65, "kind": "bunker"},
    {"name": "Novorossiysk Bunkering Hub", "lat": 44.72, "lng": 37.78, "kind": "bunker"},
    {"name": "Santos Bunkering Hub", "lat": -23.99, "lng": -46.30, "kind": "bunker"},
    {"name": "Cartagena Bunkering Hub", "lat": 10.40, "lng": -75.51, "kind": "bunker"},
    {"name": "Suez Bunkering Hub", "lat": 29.97, "lng": 32.55, "kind": "bunker"},
    {"name": "Dalian Bunkering Hub", "lat": 38.93, "lng": 121.61, "kind": "bunker"},

    # Dry docks
    {"name": "Dubai Drydocks World", "lat": 25.27, "lng": 55.05, "kind": "drydock"},
    {"name": "Keppel Shipyard – Singapore", "lat": 1.29, "lng": 103.65, "kind": "drydock"},
    {"name": "CSBC Kaohsiung Shipyard", "lat": 22.58, "lng": 120.28, "kind": "drydock"},
    {"name": "Hyundai Heavy Industries – Gunsan", "lat": 35.97, "lng": 126.68, "kind": "drydock"},
    {"name": "Hyundai Samho Heavy Industries", "lat": 34.68, "lng": 126.44, "kind": "drydock"},
    {"name": "Chantiers de l'Atlantique – Saint-Nazaire", "lat": 47.28, "lng": -2.20, "kind": "drydock"},
    {"name": "Cammell Laird – Birkenhead", "lat": 53.39, "lng": -3.00, "kind": "drydock"},
    {"name": "Navantia – Cádiz", "lat": 36.53, "lng": -6.28, "kind": "drydock"},
    {"name": "Colombo Dockyard", "lat": 6.95, "lng": 79.85, "kind": "drydock"},
    {"name": "Rio de Janeiro Dry Dock", "lat": -22.80, "lng": -43.20, "kind": "drydock"},
    {"name": "Alexandria Shipyard", "lat": 31.20, "lng": 29.88, "kind": "drydock"},
    {"name": "Balboa Shipyard – Panama City", "lat": 8.95, "lng": -79.57, "kind": "drydock"},
    {"name": "Hong Kong United Dockyards – Tsing Yi", "lat": 22.36, "lng": 114.10, "kind": "drydock"},
    {"name": "Sturrock Dry Dock – Cape Town", "lat": 33.90, "lng": 18.43, "kind": "drydock"},
    {"name": "Detyens Shipyards – Charleston", "lat": 32.83, "lng": -79.98, "kind": "drydock"},
    {"name": "Newport News Shipbuilding – Dry Dock 12", "lat": 36.98, "lng": -76.43, "kind": "drydock"},
    {"name": "Alabama Shipyard – Mobile", "lat": 30.68, "lng": -88.04, "kind": "drydock"},
    {"name": "ASMAR Shipyards – Talcahuano", "lat": -36.72, "lng": -73.12, "kind": "drydock"},
    {"name": "Sumitomo Heavy Industries – Yokosuka", "lat": 35.30, "lng": 139.67, "kind": "drydock"},
    {"name": "New Times Shipyard – Jingjiang", "lat": 32.02, "lng": 120.27, "kind": "drydock"},

    # Wet docks
    {"name": "Royal Albert Dock – London", "lat": 51.508, "lng": 0.056, "kind": "wetdock"},
    {"name": "Waalhaven – Rotterdam", "lat": 51.89, "lng": 4.45, "kind": "wetdock"},
    {"name": "Kattendijkdok – Antwerp", "lat": 51.24, "lng": 4.41, "kind": "wetdock"},
    {"name": "Le Havre Wet Docks", "lat": 49.49, "lng": 0.11, "kind": "wetdock"},
    {"name": "Hamburg Harbour Wet Docks", "lat": 53.54, "lng": 9.99, "kind": "wetdock"},
    {"name": "Kidderpore Docks – Kolkata", "lat": 22.54, "lng": 88.31, "kind": "wetdock"},
    {"name": "Cockatoo Island Wet Dock – Sydney", "lat": -33.85, "lng": 151.17, "kind": "wetdock"},
    {"name": "Erie Basin – Brooklyn", "lat": 40.67, "lng": -74.01, "kind": "wetdock"},
    {"name": "Alexandra Basin – Dublin Port", "lat": 53.34, "lng": -6.20, "kind": "wetdock"},
    {"name": "Salford Docks – Manchester", "lat": 53.47, "lng": -2.30, "kind": "wetdock"},

    # Shipyards
    {"name": "Yangzijiang Shipbuilding", "lat": 32.02, "lng": 120.27, "kind": "shipyard"},
    {"name": "CSSC Wuchang Shipbuilding", "lat": 30.55, "lng": 114.30, "kind": "shipyard"},
    {"name": "Jinling Shipyard – Nanjing", "lat": 32.06, "lng": 118.80, "kind": "shipyard"},
    {"name": "Nantong COSCO KHI Ship Engineering", "lat": 32.08, "lng": 120.86, "kind": "shipyard"},
    {"name": "Tsuneishi Shipbuilding", "lat": 34.36, "lng": 133.32, "kind": "shipyard"},
    {"name": "Oshima Shipbuilding", "lat": 32.83, "lng": 129.98, "kind": "shipyard"},
    {"name": "Onomichi Shipbuilding (Japan Marine United)", "lat": 34.41, "lng": 133.20, "kind": "shipyard"},
    {"name": "HD Hyundai Mipo Dockyard", "lat": 35.49, "lng": 129.39, "kind": "shipyard"},
    {"name": "HJ Shipbuilding & Construction (formerly Hanjin)", "lat": 35.10, "lng": 129.03, "kind": "shipyard"},
    {"name": "Sembcorp Marine – Tuas", "lat": 1.32, "lng": 103.64, "kind": "shipyard"},
    {"name": "PaxOcean Shipyard – Batam", "lat": 1.13, "lng": 104.05, "kind": "shipyard"},
    {"name": "Larsen & Toubro Shipyard – Kattupalli", "lat": 13.29, "lng": 80.32, "kind": "shipyard"},
    {"name": "Goa Shipyard Limited", "lat": 15.40, "lng": 73.83, "kind": "shipyard"},
    {"name": "Garden Reach Shipbuilders – Kolkata", "lat": 22.54, "lng": 88.31, "kind": "shipyard"},
    {"name": "ASRY – Bahrain", "lat": 26.20, "lng": 50.61, "kind": "shipyard"},
    {"name": "Abu Dhabi Ship Building (ADSB)", "lat": 24.42, "lng": 54.47, "kind": "shipyard"},
    {"name": "Lamprell – Hamriyah", "lat": 25.42, "lng": 55.46, "kind": "shipyard"},
    {"name": "Tuzla Shipyards Zone – Istanbul", "lat": 40.82, "lng": 29.35, "kind": "shipyard"},
    {"name": "RMK Marine – Tuzla", "lat": 40.82, "lng": 29.36, "kind": "shipyard"},
    {"name": "Remontowa Shipyard – Gdańsk", "lat": 54.36, "lng": 18.67, "kind": "shipyard"},
    {"name": "Crist Shipyard – Gdynia", "lat": 54.53, "lng": 18.55, "kind": "shipyard"},
    {"name": "Meyer Turku", "lat": 60.42, "lng": 22.18, "kind": "shipyard"},
    {"name": "Ulstein Verft", "lat": 62.35, "lng": 5.85, "kind": "shipyard"},
    {"name": "Vard Group – Søviknes", "lat": 62.68, "lng": 6.80, "kind": "shipyard"},
    {"name": "Astilleros Gondan", "lat": 43.55, "lng": -6.38, "kind": "shipyard"},
    {"name": "Freire Shipyard – Vigo", "lat": 42.24, "lng": -8.72, "kind": "shipyard"},
    {"name": "Fincantieri – Ancona", "lat": 43.60, "lng": 13.51, "kind": "shipyard"},
    {"name": "Fincantieri – Castellammare di Stabia", "lat": 40.70, "lng": 14.48, "kind": "shipyard"},
    {"name": "Naval Group – Lorient", "lat": 47.75, "lng": -3.37, "kind": "shipyard"},
    {"name": "STX France – Saint-Nazaire", "lat": 47.28, "lng": -2.20, "kind": "shipyard"},
    {"name": "Harland & Wolff – Belfast", "lat": 54.61, "lng": -5.90, "kind": "shipyard"},
    {"name": "Babcock Marine – Rosyth", "lat": 56.03, "lng": -3.44, "kind": "shipyard"},
    {"name": "Blohm+Voss – Hamburg", "lat": 53.54, "lng": 9.96, "kind": "shipyard"},
    {"name": "Lloyd Werft – Bremerhaven", "lat": 53.53, "lng": 8.58, "kind": "shipyard"},
    {"name": "Damen Shipyards – Schelde", "lat": 51.45, "lng": 3.83, "kind": "shipyard"},
    {"name": "Severnoye Design Bureau / Admiralty Shipyards – St. Petersburg", "lat": 59.92, "lng": 30.28, "kind": "shipyard"},
    {"name": "Sungdong Shipbuilding – Tongyeong", "lat": 34.85, "lng": 128.43, "kind": "shipyard"},
    {"name": "STX Offshore & Shipbuilding – Jinhae", "lat": 35.15, "lng": 128.68, "kind": "shipyard"},
    {"name": "Vard Braila", "lat": 45.27, "lng": 27.98, "kind": "shipyard"},
    {"name": "Damen Shipyards Mangalia", "lat": 43.81, "lng": 28.58, "kind": "shipyard"},
    {"name": "Estaleiro Atlântico Sul", "lat": -8.30, "lng": -34.93, "kind": "shipyard"},
    {"name": "Astillero Río Santiago", "lat": -34.85, "lng": -57.90, "kind": "shipyard"},
    {"name": "Karachi Shipyard & Engineering Works", "lat": 24.85, "lng": 66.98, "kind": "shipyard"},
    {"name": "Chittagong Dry Dock Limited", "lat": 22.31, "lng": 91.79, "kind": "shipyard"},
    {"name": "Colombo Dockyard – Shipbuilding Division", "lat": 6.95, "lng": 79.85, "kind": "shipyard"},
    {"name": "Wärtsilä Shipyard – Turku (historic)", "lat": 60.42, "lng": 22.18, "kind": "shipyard"},
    {"name": "Nordic Yards – Wismar", "lat": 53.90, "lng": 11.47, "kind": "shipyard"},
    {"name": "Damen Shipyards Galați", "lat": 45.44, "lng": 28.03, "kind": "shipyard"},
    {"name": "China Merchants Industry Shipyard – Shenzhen", "lat": 22.47, "lng": 113.88, "kind": "shipyard"},
    {"name": "Huangpu Wenchong Shipbuilding", "lat": 23.10, "lng": 113.47, "kind": "shipyard"},
    {"name": "Keppel Shipyard – Singapore (Shipbuilding Division)", "lat": 1.29, "lng": 103.65, "kind": "shipyard"},
    {"name": "Cosco Shipping Heavy Industry – Qidong", "lat": 31.80, "lng": 121.66, "kind": "shipyard"},
    {"name": "Fujian Southeast Shipyard", "lat": 24.98, "lng": 118.68, "kind": "shipyard"},
    {"name": "Damen Shipyards Bergum", "lat": 53.20, "lng": 6.00, "kind": "shipyard"},
    {"name": "Vard Vung Tau", "lat": 10.35, "lng": 107.08, "kind": "shipyard"},
]


def find_facility(name):
    if not name:
        return {"error": "No name given"}
    q = name.strip().lower()
    if len(q) < 2:
        return {"error": "Name too short to search"}
    combined = [{"name": p["name"], "lat": p["lat"], "lng": p["lng"], "kind": "port"} for p in PORTS] + FACILITIES
    matches = [f for f in combined if q in f["name"].lower()]
    if not matches:
        return {"error": f"No port or facility found matching '{name}'"}
    return {"count": len(matches), "facilities": matches[:10]}


def find_port_by_name(query):
    if not query:
        return None
    query_lower = query.lower()
    for p in PORTS:
        if query_lower in p["name"].lower():
            return p
    return None


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_compass(lat1, lng1, lat2, lng2):
    y = math.sin(math.radians(lng2 - lng1)) * math.cos(math.radians(lat2))
    x = (
        math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
        - math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(math.radians(lng2 - lng1))
    )
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    directions = [
        "north", "north-northeast", "northeast", "east-northeast",
        "east", "east-southeast", "southeast", "south-southeast",
        "south", "south-southwest", "southwest", "west-southwest",
        "west", "west-northwest", "northwest", "north-northwest",
    ]
    return directions[round(bearing / 22.5) % 16]


def port_direction(from_port, to_port):
    a = find_port_by_name(from_port)
    b = find_port_by_name(to_port)
    if not a:
        return {"error": f"No port found matching '{from_port}'"}
    if not b:
        return {"error": f"No port found matching '{to_port}'"}
    return {
        "from": a["name"],
        "to": b["name"],
        "distance_km": round(haversine_km(a["lat"], a["lng"], b["lat"], b["lng"]), 1),
        "direction_from_origin": bearing_compass(a["lat"], a["lng"], b["lat"], b["lng"]),
    }


# Flag state from the MMSI. The first 3 digits of a ship's MMSI are its
# Maritime Identification Digits (MID), an ITU-assigned country code.
# Some countries own several MIDs, so we list them per country and invert.
FLAG_MIDS = {
    # Europe
    "Albania": [201], "Andorra": [202], "Austria": [203],
    "Portugal": [204, 255, 263], "Belgium": [205], "Belarus": [206],
    "Bulgaria": [207], "Vatican City": [208], "Cyprus": [209, 210, 212],
    "Germany": [211, 218], "Georgia": [213], "Moldova": [214],
    "Malta": [215, 229, 248, 249, 256], "Armenia": [216], "Denmark": [219, 220],
    "Spain": [224, 225], "France": [226, 227, 228], "Finland": [230],
    "Faroe Islands": [231], "United Kingdom": [232, 233, 234, 235],
    "Gibraltar": [236], "Greece": [237, 239, 240, 241], "Croatia": [238],
    "Morocco": [242], "Hungary": [243], "Netherlands": [244, 245, 246],
    "Italy": [247], "Ireland": [250], "Iceland": [251], "Liechtenstein": [252],
    "Luxembourg": [253], "Monaco": [254], "Norway": [257, 258, 259],
    "Poland": [261], "Montenegro": [262], "Romania": [264], "Sweden": [265, 266],
    "Slovakia": [267], "San Marino": [268], "Switzerland": [269],
    "Czechia": [270], "Turkey": [271], "Ukraine": [272], "Russia": [273],
    "North Macedonia": [274], "Latvia": [275], "Estonia": [276],
    "Lithuania": [277], "Slovenia": [278], "Serbia": [279],
    # North America and Caribbean
    "Anguilla": [301], "United States": [303, 338, 366, 367, 368, 369],
    "Antigua and Barbuda": [304, 305], "Curaçao / Sint Maarten / Bonaire": [306],
    "Aruba": [307], "Bahamas": [308, 309, 311], "Bermuda": [310],
    "Belize": [312], "Barbados": [314], "Canada": [316],
    "Cayman Islands": [319], "Costa Rica": [321], "Cuba": [323],
    "Dominica": [325], "Dominican Republic": [327], "Guadeloupe": [329],
    "Grenada": [330], "Greenland": [331], "Guatemala": [332],
    "Honduras": [334], "Haiti": [336], "Jamaica": [339],
    "Saint Kitts and Nevis": [341], "Saint Lucia": [343], "Mexico": [345],
    "Martinique": [347], "Montserrat": [348], "Nicaragua": [350],
    "Panama": [351, 352, 353, 354, 355, 356, 357, 370, 371, 372, 373, 374],
    "Puerto Rico": [358], "El Salvador": [359],
    "Saint Pierre and Miquelon": [361], "Trinidad and Tobago": [362],
    "Turks and Caicos Islands": [364],
    "Saint Vincent and the Grenadines": [375, 376, 377],
    "British Virgin Islands": [378], "US Virgin Islands": [379],
    # Asia
    "Afghanistan": [401], "Saudi Arabia": [403], "Bangladesh": [405],
    "Bahrain": [408], "Bhutan": [410], "China": [412, 413, 414],
    "Taiwan": [416], "Sri Lanka": [417], "India": [419], "Iran": [422],
    "Azerbaijan": [423], "Iraq": [425], "Israel": [428], "Japan": [431, 432],
    "Turkmenistan": [434], "Kazakhstan": [436], "Uzbekistan": [437],
    "Jordan": [438], "South Korea": [440, 441], "Palestine": [443],
    "North Korea": [445], "Kuwait": [447], "Lebanon": [450],
    "Kyrgyzstan": [451], "Macao": [453], "Maldives": [455], "Mongolia": [457],
    "Nepal": [459], "Oman": [461], "Pakistan": [463], "Qatar": [466],
    "Syria": [468], "United Arab Emirates": [470, 471], "Tajikistan": [472],
    "Yemen": [473, 475], "Hong Kong": [477], "Bosnia and Herzegovina": [478],
    # Oceania
    "French Southern Territories": [501, 607], "Antarctica": [618, 635],
    "Australia": [503], "Myanmar": [506], "Brunei": [508],
    "Micronesia": [510], "Palau": [511], "New Zealand": [512],
    "Cambodia": [514, 515], "Christmas Island": [516], "Cook Islands": [518],
    "Fiji": [520], "Cocos Islands": [523], "Indonesia": [525],
    "Kiribati": [529], "Laos": [531], "Malaysia": [533],
    "Northern Mariana Islands": [536], "Marshall Islands": [538],
    "New Caledonia": [540], "Niue": [542], "Nauru": [544],
    "French Polynesia": [546], "Philippines": [548],
    "Papua New Guinea": [553], "Pitcairn Islands": [555],
    "Solomon Islands": [557], "American Samoa": [559], "Samoa": [561],
    "Singapore": [563, 564, 565, 566], "Thailand": [567], "Tonga": [570],
    "Tuvalu": [572], "Vietnam": [574], "Vanuatu": [576, 577],
    "Wallis and Futuna": [578],
    # Africa
    "South Africa": [601], "Angola": [603], "Algeria": [605],
    "Ascension Island": [608], "Burundi": [609], "Benin": [610],
    "Botswana": [611], "Central African Republic": [612], "Cameroon": [613],
    "Congo": [615], "Comoros": [616, 620], "Cabo Verde": [617],
    "Côte d'Ivoire": [619], "Djibouti": [621], "Egypt": [622],
    "Ethiopia": [624], "Eritrea": [625], "Gabon": [626], "Ghana": [627],
    "Gambia": [629], "Guinea-Bissau": [630], "Equatorial Guinea": [631],
    "Guinea": [632], "Burkina Faso": [633], "Kenya": [634],
    "Liberia": [636, 637], "Libya": [642], "Lesotho": [644],
    "Mauritius": [645], "Madagascar": [647], "Mali": [649],
    "Mozambique": [650], "Mauritania": [654], "Malawi": [655],
    "Niger": [656], "Nigeria": [657], "Namibia": [659], "Réunion": [660],
    "Rwanda": [661], "Sudan": [662], "Senegal": [663], "Seychelles": [664],
    "Saint Helena": [665], "Somalia": [666], "Sierra Leone": [667],
    "São Tomé and Príncipe": [668], "Eswatini": [669], "Chad": [670],
    "Togo": [671], "Tunisia": [672], "Tanzania": [674, 677], "Uganda": [675],
    "DR Congo": [676], "Zambia": [678], "Zimbabwe": [679],
    # South America
    "Argentina": [701], "Brazil": [710], "Bolivia": [720], "Chile": [725],
    "Colombia": [730], "Ecuador": [735], "Falkland Islands": [740],
    "French Guiana": [745], "Guyana": [750], "Paraguay": [755],
    "Peru": [760], "Suriname": [765], "Uruguay": [770], "Venezuela": [775],
}
MID_TO_FLAG = {mid: country for country, mids in FLAG_MIDS.items() for mid in mids}


def flag_from_mmsi(mmsi):
    try:
        return MID_TO_FLAG.get(int(str(mmsi).zfill(9)[:3]))
    except (TypeError, ValueError):
        return None

# In-memory store: latest known info per ship, keyed by MMSI.
# A background task keeps this updated forever; /ships just reads
# whatever's currently in here at the moment it's asked.
live_ships: dict[int, dict] = {}

# Departure log persisted to disk so it survives restarts.
# Keyed by MMSI as text (JSON keys are strings).
DEPARTURES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "departures.json")
try:
    with open(DEPARTURES_FILE) as f:
        DEPARTURES = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    DEPARTURES = {}


def save_departures():
    try:
        tmp = DEPARTURES_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(DEPARTURES, f)
        os.replace(tmp, DEPARTURES_FILE)
    except OSError as e:
        print(f"Could not save departures: {e}")

STATUS_MAP = {
    0: "moving", 1: "anchored-sea", 2: "anchored-sea", 3: "anchored-sea",
    4: "anchored-sea", 5: "anchored-port", 6: "anchored-sea", 7: "moving",
    8: "moving",
}

def format_eta(eta):
    # Month 0 / Hour 24 / Minute 60 are AIS's "not given" sentinel values.
    if not eta:
        return None
    month, day = eta.get("Month"), eta.get("Day")
    if not month or not day:
        return None
    text = f"{month:02d}-{day:02d}"
    hour, minute = eta.get("Hour"), eta.get("Minute")
    if hour is not None and hour <= 23 and minute is not None and minute <= 59:
        text += f" {hour:02d}:{minute:02d} UTC"
    return text


def match_destination_port(destination):
    # Destination is free text typed by a human — messy on purpose.
    # Only match exactly, or as a substantial substring, to avoid false matches.
    if not destination:
        return None
    dest = destination.strip().lower()
    if len(dest) < 3:
        return None
    for p in PORTS:
        if p["name"].strip().lower() == dest:
            return p
    best = None
    for p in PORTS:
        name = p["name"].strip().lower()
        if len(name) >= 4 and (name in dest or dest in name):
            if best is None or len(name) > len(best["name"]):
                best = p
    return best

def map_ship_type(code):
    # AIS ShipType is a numeric code in ranges, not a flat lookup table —
    # e.g. every value 70-79 means some flavor of cargo ship.
    if code is None:
        return "unknown"
    if 60 <= code <= 69:
        return "passenger"
    if 70 <= code <= 79:
        return "cargo"
    if 80 <= code <= 89:
        return "tanker"
    if code == 30:
        return "fishing"
    if code in (31, 32, 52):
        return "tug"
    if code == 36 or code == 37:
        return "pleasure"
    if code == 50 or code == 51 or code == 55:
        return "official"
    return "other"

async def listen_to_ais():
    async with websockets.connect("wss://stream.aisstream.io/v0/stream") as ws:
        subscribe_message = {
            "APIKey": API_KEY,
            # North Sea / English Channel — busy real shipping lanes,
            # keeps ship count manageable instead of the whole world firehose.
            "BoundingBoxes": [[[49, -2], [54, 9]]],
        }
        await ws.send(json.dumps(subscribe_message))

        async for message in ws:
            data = json.loads(message)
            message_type = data.get("MessageType")

            if message_type == "PositionReport":
                meta = data["MetaData"]
                report = data["Message"]["PositionReport"]
                mmsi = meta["MMSI"]

                # Merge into whatever's already there for this ship
                # (e.g. a vessel_type saved from a ShipStaticData message)
                # instead of replacing the whole record.
                existing = live_ships.get(mmsi, {})
                if "departure_port" not in existing and str(mmsi) in DEPARTURES:
                    existing = {**existing, **DEPARTURES[str(mmsi)]}

                # Departure detection: the moment a ship flips from anchored-in-port
                # to moving is the real moment it left. Log the nearest real port to
                # its PREVIOUS position (where it just was), not its new one. Only
                # fires going forward — nothing before this feature existed is known.
                new_status = STATUS_MAP.get(report.get("NavigationalStatus"), "anchored-sea")
                if existing.get("status") == "anchored-port" and new_status == "moving":
                    old_lat, old_lng = existing.get("lat"), existing.get("lng")
                    if old_lat is not None and old_lng is not None:
                        nearest, nearest_dist = None, None
                        for p in PORTS:
                            d = haversine_km(old_lat, old_lng, p["lat"], p["lng"])
                            if nearest_dist is None or d < nearest_dist:
                                nearest_dist, nearest = d, p
                        if nearest and nearest_dist <= 15:
                            existing["departure_port"] = {"name": nearest["name"], "lat": nearest["lat"], "lng": nearest["lng"]}
                            existing["departure_time"] = datetime.now(timezone.utc).isoformat()
                            DEPARTURES[str(mmsi)] = {
                                "departure_port": existing["departure_port"],
                                "departure_time": existing["departure_time"],
                            }
                            save_departures()

                live_ships[mmsi] = {
                    **existing,
                    "mmsi": mmsi,
                    "flag": flag_from_mmsi(mmsi),
                    "name": (meta.get("ShipName") or "Unknown").strip(),
                    "lat": meta["latitude"],
                    "lng": meta["longitude"],
                    "type": "Vessel",
                    "status": STATUS_MAP.get(report.get("NavigationalStatus"), "anchored-sea"),
                    "speed": report.get("Sog"),
                    "heading": report.get("Cog"),
                    "last_seen": datetime.now(timezone.utc),
                }

            elif message_type == "ShipStaticData":
                meta = data["MetaData"]
                static = data["Message"]["ShipStaticData"]
                mmsi = meta["MMSI"]

                # Only attach vessel type to ships we've already seen a
                # position for — no point creating a ship entry with a
                # type but no location.
                if mmsi in live_ships:
                    live_ships[mmsi]["vessel_type"] = map_ship_type(static.get("Type"))
                    dim = static.get("Dimension") or {}
                    a, b, c, d = dim.get("A"), dim.get("B"), dim.get("C"), dim.get("D")
                    live_ships[mmsi]["length_m"] = (a + b) if a is not None and b is not None and (a + b) > 0 else None
                    live_ships[mmsi]["beam_m"] = (c + d) if c is not None and d is not None and (c + d) > 0 else None
                    imo = static.get("ImoNumber")
                    live_ships[mmsi]["imo"] = imo if imo else None
                    call_sign = (static.get("CallSign") or "").strip()
                    live_ships[mmsi]["call_sign"] = call_sign or None
                    destination = (static.get("Destination") or "").strip()
                    live_ships[mmsi]["destination"] = destination or None
                    live_ships[mmsi]["eta"] = format_eta(static.get("Eta"))
                    dest_port = match_destination_port(destination)
                    live_ships[mmsi]["destination_port"] = (
                        {"name": dest_port["name"], "lat": dest_port["lat"], "lng": dest_port["lng"]}
                        if dest_port else None
                    )


# Ships not heard from for this long are dropped from the live list.
# Kept well above DARK_THRESHOLD_MINUTES (20) so silent ships are flagged before they vanish.
SHIP_EXPIRY_MINUTES = 60       # ships that drift out through the edge of the tracked area
DARK_RETENTION_HOURS = 24      # ships that go silent well inside the area stay visible (as dark fleet) this long
EDGE_MARGIN_DEG = 0.5
TRACKED_BOX = (49, -2, 54, 9)  # lat_min, lng_min, lat_max, lng_max; must match the AIS subscription


def expiry_seconds(ship):
    lat_min, lng_min, lat_max, lng_max = TRACKED_BOX
    lat, lng = ship.get("lat"), ship.get("lng")
    if lat is None or lng is None:
        return SHIP_EXPIRY_MINUTES * 60
    near_edge = (
        lat < lat_min + EDGE_MARGIN_DEG or lat > lat_max - EDGE_MARGIN_DEG
        or lng < lng_min + EDGE_MARGIN_DEG or lng > lng_max - EDGE_MARGIN_DEG
    )
    return SHIP_EXPIRY_MINUTES * 60 if near_edge else DARK_RETENTION_HOURS * 3600


async def prune_stale_ships_loop():
    while True:
        await asyncio.sleep(60)
        now = datetime.now(timezone.utc)
        stale = [
            mmsi for mmsi, s in list(live_ships.items())
            if s.get("last_seen") and (now - s["last_seen"]).total_seconds() > expiry_seconds(s)
        ]
        for mmsi in stale:
            live_ships.pop(mmsi, None)
        if stale:
            print(f"Expired {len(stale)} stale ships; {len(live_ships)} remain")


async def ais_background_loop():
    # The connection will eventually drop on its own — reconnect
    # automatically instead of the feed silently dying forever.
    while True:
        try:
            await listen_to_ais()
        except Exception as e:
            print(f"AIS connection dropped, reconnecting in 5s: {e}")
            await asyncio.sleep(5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Starts the AIS listener once, when the server boots, running
    # alongside normal request handling for the server's whole lifetime.
    fetch_ports()
    task = asyncio.create_task(ais_background_loop())
    prune_task = asyncio.create_task(prune_stale_ships_loop())
    yield
    task.cancel()
    prune_task.cancel()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ships")
def get_ships():
    return flag_dark_ships(list(live_ships.values()))

@app.get("/ships/dark-fleet")
def get_dark_fleet():
    all_ships = flag_dark_ships(list(live_ships.values()))
    return [s for s in all_ships if s["is_dark_flagged"]]



class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


def query_ships(vessel_type=None, status=None, is_dark_flagged=None,
                 min_minutes_since_update=None, near_port=None, radius_km=None,
                 has_destination=None, has_departure=None, flag=None,
                 departed_from=None, destination_contains=None):
    ships = flag_dark_ships(list(live_ships.values()))

    if vessel_type:
        ships = [s for s in ships if s.get("vessel_type") == vessel_type]
    if status:
        ships = [s for s in ships if s.get("status") == status]
    if has_destination is not None:
        ships = [s for s in ships if bool(s.get("destination")) == has_destination]
    if has_departure is not None:
        ships = [s for s in ships if bool(s.get("departure_port")) == has_departure]
    if is_dark_flagged is not None:
        ships = [s for s in ships if s.get("is_dark_flagged") == is_dark_flagged]
    if min_minutes_since_update is not None:
        ships = [s for s in ships if s.get("minutes_since_update", 0) >= min_minutes_since_update]

    if near_port:
        port = find_port_by_name(near_port)
        if not port:
            return {"error": f"No port found matching '{near_port}'"}
        r = radius_km or 20
        ships = [
            s for s in ships
            if haversine_km(port["lat"], port["lng"], s["lat"], s["lng"]) <= r
        ]

    by_status = dict(Counter(s.get("status") for s in ships))
    by_type = dict(Counter(s.get("vessel_type") or "unknown" for s in ships))

    # Cap results so we don't blow past the model's context on a busy fleet.
    # last_seen is a datetime object, so convert it to text so json.dumps() works.
    trimmed = []
    for s in ships[:20]:
        s_copy = dict(s)
        if "last_seen" in s_copy:
            s_copy["last_seen"] = str(s_copy["last_seen"])
        trimmed.append(s_copy)
    # Every match (id, name, position only) so the globe can highlight the whole set.
    # Past 500 ships a highlight stops being meaningful, so send none.
    highlight = []
    if len(ships) <= 500:
        highlight = [
            {"mmsi": s.get("mmsi"), "name": s.get("name"), "lat": s["lat"], "lng": s["lng"]}
            for s in ships
        ]
    return {"count": len(ships), "by_status": by_status, "by_type": by_type, "ships": trimmed, "highlight": highlight}


def slim_for_model(result):
    # The model only needs a compact summary. The full ship list still goes to the globe.
    if "ships" not in result:
        return result
    keep = ("name", "flag", "status", "vessel_type", "speed", "minutes_since_update", "destination", "departure_port")
    return {
        "count": result["count"],
        "by_status": result.get("by_status"),
        "by_type": result.get("by_type"),
        "sample_ships": [{k: s.get(k) for k in keep} for s in result["ships"][:5]],
    }


def groq_post(payload):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    resp = None
    for attempt in range(4):
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
        if resp.status_code != 429:
            return resp
        # Rate limited: wait as long as Groq suggests, then try again.
        match = re.search(r"try again in ([\d.]+)s", resp.text)
        wait = float(match.group(1)) + 0.5 if match else 5
        time.sleep(min(wait, 15))
    return resp


def find_ship(name=None, imo=None):
    if not name and not imo:
        return {"error": "No ship name or IMO given"}
    matches = flag_dark_ships(list(live_ships.values()))
    if name:
        name_lower = name.lower()
        matches = [s for s in matches if name_lower in (s.get("name") or "").lower()]
    if imo:
        try:
            imo_int = int(imo)
            matches = [s for s in matches if s.get("imo") == imo_int]
        except (TypeError, ValueError):
            pass
    if not matches:
        return {"error": "No live ship found matching that name/IMO. It may be outside the tracked North Sea / English Channel region, or its details may differ from what was asked."}

    results = []
    for ship in matches[:10]:
        nearest = None
        nearest_dist = None
        for p in PORTS:
            d = haversine_km(ship["lat"], ship["lng"], p["lat"], p["lng"])
            if nearest_dist is None or d < nearest_dist:
                nearest_dist = d
                nearest = p
        ship_copy = dict(ship)
        if "last_seen" in ship_copy:
            ship_copy["last_seen"] = str(ship_copy["last_seen"])
        ship_copy["nearest_port"] = nearest["name"] if nearest else None
        ship_copy["nearest_port_distance_km"] = round(nearest_dist, 1) if nearest_dist is not None else None
        ship_copy["nearest_port_direction"] = bearing_compass(ship["lat"], ship["lng"], nearest["lat"], nearest["lng"]) if nearest else None
        results.append(ship_copy)

    return {"count": len(matches), "ships": results}


FACILITY_TOOL = {
    "type": "function",
    "function": {
        "name": "find_facility",
        "description": (
            "Look up a specific port, lighthouse, shipyard, ship recycling yard, "
            "bunkering station, dry dock, or wet dock by name, to get its real "
            "location so it can be highlighted on the map."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The facility's name, e.g. 'Rotterdam' or 'Portland Head Light'"},
            },
            "required": ["name"],
        },
    },
}


CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_ships",
            "description": (
                "Filter the live tracked fleet by vessel type, movement status, "
                "dark-fleet flag, how long since last AIS update, and/or proximity "
                "to a named port anywhere in the world. Returns the total count, a "
                "breakdown by status and vessel type, and up to 5 sample ships."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vessel_type": {
                        "type": ["string", "null"],
                        "enum": ["cargo", "tanker", "fishing", "passenger", "tug", "pleasure", "official", "other", "unknown", None],
                    },
                    "status": {
                        "type": ["string", "null"],
                        "enum": ["moving", "anchored-port", "anchored-sea", None],
                    },
                    "is_dark_flagged": {"type": ["boolean", "null"]},
                    "min_minutes_since_update": {"type": ["number", "null"]},
                    "near_port": {"type": ["string", "null"], "description": "A port name, e.g. 'Rotterdam'"},
                    "radius_km": {"type": ["number", "null"], "description": "Search radius around near_port, default 20km"},
                    "has_destination": {"type": ["boolean", "null"], "description": "True to only return ships that have broadcast a destination in their AIS static data"},
                    "has_departure": {"type": ["boolean", "null"], "description": "True to only return ships with a logged real departure-port event (detected live, not from AIS broadcast)"},
                    "flag": {"type": ["string", "null"], "description": "Flag state country name, e.g. 'Germany', 'Netherlands', 'United Kingdom', 'Panama'"},
                    "departed_from": {"type": ["string", "null"], "description": "Only ships whose logged departure port name contains this text, e.g. 'Antwerp'"},
                    "destination_contains": {"type": ["string", "null"], "description": "Only ships whose broadcast destination text or matched destination port contains this text, e.g. 'Rotterdam'"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "port_direction",
            "description": "Get the real distance and compass direction from one named port to another.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_port": {"type": "string"},
                    "to_port": {"type": "string"},
                },
                "required": ["from_port", "to_port"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_ship",
            "description": (
                "Look up a specific live ship by name and/or IMO number. Returns full "
                "details for every match (up to 10) — use the imo parameter to "
                "disambiguate when two ships have similar names. Always use this for "
                "questions about a named ship — never assume a ship's name refers to "
                "a real-world place."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The ship's name, e.g. 'RATINGEN'. Optional if imo is given."},
                    "imo": {"type": "string", "description": "The ship's IMO number, if known — use to disambiguate between similarly-named ships."},
                },
            },
        },
    },
    FACILITY_TOOL,
]


@app.post("/chat")
def chat(req: ChatRequest):
    if not GROQ_API_KEY:
        return {"reply": "Chat isn't configured yet (missing GROQ_API_KEY in .env).", "ships": []}

    system_prompt = (
        "You are a maritime fleet assistant. Answer questions about the ships currently "
        "being tracked live via AIS by calling the query_ships tool. Never guess ship data "
        "yourself. You may call the tool several times (for example once per port when "
        "comparing ports). Keep answers concise, mention ship names and key facts (status, vessel "
        "type, time since last update), and say plainly if zero ships matched. Note that "
        "live position data only exists for ships in the North Sea / English Channel region, "
        "even though port lookups cover the whole world. When comparing two named ports "
        "(e.g. which is busier), call port_direction to state the real distance and "
        "compass direction between them rather than guessing. For questions about a specific "
        "named ship (e.g. 'nearest port to X'), always call find_ship — never assume the name "
        "refers to a real-world place, since it's a ship you're tracking live. If find_ship returns "
        "more than one match, use the returned IMO numbers to pick the right one rather than "
        "guessing — never claim a ship does or doesn't have a particular IMO unless you can see "
        "it in the actual returned data. For questions about a "
        "specific named port, lighthouse, shipyard, recycling yard, bunkering station, or dry/wet dock, "
        "call find_facility to get its real location. If the person says 'point to', 'find' or "
        "'where is' a name and you cannot tell whether it is a ship or a facility, call BOTH "
        "find_ship and find_facility before concluding it does not exist, because most names "
        "that are not ports are ship names. Only say a name was not found after checking both. "
        "When asked which port is "
        "busiest, always also look up at least one other nearby port and mention it by name "
        "for comparison, e.g. 'For comparison, X has only N ships nearby.' Never write two or "
        "more numbers on the same line without a comma or a line break between them — "
        "write 'Moving: 37, Anchored-port: 20, Anchored-sea: 8', not 'Moving: 37 Anchored-port: 20'. "
        "Do not list individual sample ships unless the person specifically asks for named ships — "
        "stick to counts and breakdowns by status/type. When the person refers back to a previous "
        "result — 'show them', 'point to them', 'highlight those' — call query_ships again with the "
        "exact same filters as the query that produced that result. Never call it with no filters "
        "just because the person said 'them' or 'those' — that would silently show the entire fleet "
        "instead of what they actually asked about. "
        "Formatting rules: never use Markdown tables, headings (#) or code blocks, and never use "
        "'*' bullets. Write short plain lines, one item per line, like "
        "'VICTORIA — Netherlands, 4.5 kn'. Use '- ' at the start of a line for lists. "
        "Bold with **text** is fine."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in req.history[-10:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": req.message})

    matched_ships_map = {}
    matched_facilities_map = {}
    tool_call_count = 0
    MAX_ROUNDS = 5

    for round_number in range(MAX_ROUNDS + 1):
        # On the last round, forbid more tool calls so the model must write its answer.
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "tools": CHAT_TOOLS,
            "tool_choice": "auto" if round_number < MAX_ROUNDS else "none",
        }
        try:
            resp = groq_post(payload)
            if resp.status_code != 200:
                print("GROQ ERROR:", resp.status_code, resp.text[:800])
                return {"reply": f"Chat request failed ({resp.status_code}): {resp.text[:300]}", "ships": [], "count": 0}
        except Exception as e:
            return {"reply": f"Chat request failed: {e}", "ships": [], "count": 0}

        choice = resp.json()["choices"][0]["message"]
        tool_calls = choice.get("tool_calls")

        if not tool_calls:
            final_text = choice.get("content") or ""
            return {
                "reply": final_text,
                "ships": list(matched_ships_map.values()),
                "facilities": list(matched_facilities_map.values()),
            }

        messages.append({
            "role": "assistant",
            "content": choice.get("content"),
            "tool_calls": tool_calls,
        })
        for call in tool_calls:
            tool_call_count += 1
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
                fn_name = call["function"]["name"]
                if fn_name == "port_direction":
                    result = port_direction(**args)
                elif fn_name == "find_ship":
                    result = find_ship(**args)
                elif fn_name == "find_facility":
                    result = find_facility(**args)
                else:
                    result = query_ships(**args)
            except Exception as e:
                result = {"error": f"tool call failed: {e}"}
            print("TOOL CALL:", call["function"]["name"], call["function"]["arguments"], "->", str(result)[:300])
            # Only accumulate when the result is a complete (non-truncated) match set —
            # e.g. 2 real ships found, not a 20-ship sample of a 1,000+ broad query.
            if "highlight" in result:
                for s in result["highlight"]:
                    matched_ships_map[s["mmsi"]] = s
            elif "ships" in result and result.get("count") == len(result.get("ships", [])):
                for s in result["ships"]:
                    matched_ships_map[s["mmsi"]] = s
            if "facilities" in result and result.get("count") == len(result.get("facilities", [])):
                for f in result["facilities"]:
                    matched_facilities_map[(f["name"], f["kind"])] = f
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(slim_for_model(result)),
            })

    return {
        "reply": "Sorry, I couldn't finish that question.",
        "ships": list(matched_ships_map.values()),
        "facilities": list(matched_facilities_map.values()),
    }