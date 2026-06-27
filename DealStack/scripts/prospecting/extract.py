#!/usr/bin/env python3
"""
Maps Lead Extractor - Extrai leads do OpenStreetMap via Overpass API.
Gera JSON compatível com sales-prospecting skill.
"""
import sys
import json
import argparse
import time
import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ===== CATEGORIAS PRÉ-DEFINIDAS =====
CATEGORIES_PATH = Path(__file__).parent.parent.parent / "sales-prospecting" / "references" / "categories.json"
with open(CATEGORIES_PATH, encoding="utf-8") as f:
    CATEGORIES = json.load(f)

# Mapeamento tipo OSM -> nome amigável para sales-prospecting
TYPE_LABELS = {
    # Hospitality
    "hotel": "Hotel", "guest_house": "Pousada", "hostel": "Hostel",
    "motel": "Motel", "camp_site": "Camping", "apartment": "Apartamento",
    "bed_and_breakfast": "Bed & Breakfast",
    # Retail
    "clothes": "Loja de roupas", "boutique": "Boutique", "fashion": "Moda",
    "shoes": "Sapataria", "jewelry": "Joalheria", "supermarket": "Supermercado",
    "convenience": "Conveniência", "mall": "Shopping", "department_store": "Magazine",
    "electronics": "Eletrônicos", "mobile_phone": "Celulares", "computer": "Informática",
    "books": "Livraria", "gift": "Presentes", "florist": "Floricultura",
    "optician": "Ótica", "cosmetics": "Cosméticos", "perfumery": "Perfumaria",
    "furniture": "Móveis", "hardware": "Ferragens", "bakery": "Padaria",
    "butcher": "Açougue", "cheese": "Queijaria", "chocolate": "Chocolateria",
    "coffee": "Café", "tea": "Casa de chá", "wine": "Adega", "alcohol": "Bebidas",
    # Food
    "restaurant": "Restaurante", "cafe": "Café", "fast_food": "Fast Food",
    "ice_cream": "Sorveteria", "food_court": "Praça de alimentação",
    "bistro": "Bistrô", "brasserie": "Brasserie", "pizzeria": "Pizzaria",
    "steakhouse": "Churrascaria", "sushi": "Japonês", "noodle": "Macarrão",
    "burger": "Hamburgueria", "kebab": "Kebab", "chicken": "Frango",
    "seafood": "Frutos do mar", "vegetarian": "Vegetariano", "vegan": "Vegano",
    "bar": "Bar", "pub": "Pub",
    # Health
    "dentist": "Dentista", "doctor": "Médico", "clinic": "Clínica",
    "pharmacy": "Farmácia", "optometrist": "Ótica", "physiotherapist": "Fisioterapeuta",
    "veterinarian": "Veterinário", "hospital": "Hospital",
    # Beauty
    "hairdresser": "Salão de beleza", "beauty": "Beleza", "spa": "Spa",
    "nails": "Manicure", "massage": "Massagem", "tattoo": "Tatuagem",
    "piercing": "Piercing", "solarium": "Bronzeamento", "barber": "Barbearia",
    # Automotive
    "car_repair": "Oficina", "car_wash": "Lava-rápido", "gas_station": "Posto",
    "car_rental": "Locadora", "parking": "Estacionamento",
    # Services
    "laundry": "Lavanderia", "locksmith": "Chaveiro", "tailor": "Alfaiataria",
    "bank": "Banco", "atm": "Caixa eletrônico", "insurance": "Seguradora",
    "real_estate": "Imobiliária", "lawyer": "Advogado", "accountant": "Contador",
    # Education
    "school": "Escola", "university": "Universidade", "kindergarten": "Creche",
    "driving_school": "Autoescola", "language_school": "Escola de idiomas",
    # Entertainment
    "cinema": "Cinema", "theatre": "Teatro", "nightclub": "Balada",
    "bowling_alley": "Boliche", "museum": "Museu", "gallery": "Galeria",
    "zoo": "Zoológico", "aquarium": "Aquário", "theme_park": "Parque temático",
}


# ===== UTILS =====
def http_get(url: str, timeout: int = 30) -> dict:
    """GET request com retry simples."""
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes-MapsLeadExtractor/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return {}


def geocode(location: str) -> Tuple[float, float]:
    """Geocodifica endereço via Nominatim (OpenStreetMap)."""
    # Se já é "lat,lon"
    if "," in location and all(c.replace(".", "").replace("-", "").isdigit() for c in location.split(",")):
        lat, lon = map(float, location.split(","))
        return lat, lon

    url = f"https://nominatim.openstreetmap.org/search?{urllib.parse.urlencode({'q': location, 'format': 'json', 'limit': 1})}"
    data = http_get(url)
    if not data:
        raise ValueError(f"Localização não encontrada: {location}")
    return float(data[0]["lat"]), float(data[0]["lon"])


def build_overpass_query(lat: float, lon: float, types: List[str], radius: int) -> str:
    """Constrói query Overpass para os tipos dados."""
    # Agrupa por key principal (tourism, shop, amenity, etc.)
    key_groups: Dict[str, List[str]] = {}
    for t in types:
        # Heurística simples de key baseado no tipo
        if t in {"hotel", "guest_house", "hostel", "motel", "camp_site", "apartment", "bed_and_breakfast"}:
            key = "tourism"
        elif t in {"restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream", "food_court",
                   "bistro", "brasserie", "pizzeria", "steakhouse", "sushi", "noodle",
                   "burger", "kebab", "chicken", "seafood", "vegetarian", "vegan"}:
            key = "amenity"
        elif t in {"bakery", "butcher", "cheese", "chocolate", "coffee", "tea", "wine", "alcohol"}:
            key = "shop"
        elif t in {"dentist", "doctor", "clinic", "pharmacy", "optometrist", "physiotherapist",
                   "veterinarian", "hospital"}:
            key = "amenity"
        elif t in {"hairdresser", "beauty", "spa", "nails", "massage", "tattoo", "piercing",
                   "solarium", "barber"}:
            key = "shop" if t in {"hairdresser", "beauty"} else "amenity"
        elif t in {"car_repair", "car_wash", "gas_station", "car_rental", "parking",
                   "charging_station"}:
            key = "amenity" if t != "parking" else "amenity"
        elif t in {"supermarket", "convenience", "mall", "department_store", "electronics",
                   "mobile_phone", "computer", "books", "gift", "florist", "optician",
                   "cosmetics", "perfumery", "furniture", "hardware", "clothes", "boutique",
                   "fashion", "shoes", "jewelry"}:
            key = "shop"
        else:
            key = "shop"  # fallback

        key_groups.setdefault(key, []).append(t)

    # Monta query
    parts = []
    for key, vals in key_groups.items():
        regex = "|".join(vals)
        parts.append(f'  node["{key}"~"{regex}"](around:{radius},{lat},{lon});')
        parts.append(f'  way["{key}"~"{regex}"](around:{radius},{lat},{lon});')
        parts.append(f'  relation["{key}"~"{regex}"](around:{radius},{lat},{lon});')

    query = f"""[out:json][timeout:25];
(
{chr(10).join(parts)}
);
out center tags;"""
    return query


def query_overpass(query: str) -> dict:
    """Executa query no Overpass API."""
    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(url, data=data,
        headers={"User-Agent": "Hermes-MapsLeadExtractor/1.0", "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_lead_from_element(el: dict, lat: float, lon: float) -> Optional[dict]:
    """Extrai lead padronizado de um elemento OSM."""
    tags = el.get("tags", {})
    name = tags.get("name") or tags.get("official_name") or tags.get("alt_name") or tags.get("loc_name")
    if not name:
        return None

    # Coordenadas
    if el["type"] == "node":
        el_lat, el_lon = el["lat"], el["lon"]
    else:
        center = el.get("center", {})
        el_lat, el_lon = center.get("lat", lat), center.get("lon", lon)

    # Endereço
    addr_parts = []
    for k in ["addr:housenumber", "addr:street", "addr:suburb", "addr:city", "addr:state", "addr:postcode"]:
        if tags.get(k):
            addr_parts.append(tags[k])
    address = ", ".join(addr_parts) if addr_parts else f"Próximo a {lat:.4f}, {lon:.4f}"

    # Tipo principal
    osm_type = None
    for k in ["tourism", "shop", "amenity", "craft", "office", "building"]:
        if tags.get(k):
            osm_type = tags[k]
            break

    # Label amigável
    business_type = TYPE_LABELS.get(osm_type, osm_type or "Negócio")

    lead = {
        "lead_name": name.strip(),
        "business_type": business_type,
        "location": address,
        "phone": tags.get("phone") or tags.get("contact:phone") or tags.get("mobile"),
        "email": tags.get("email") or tags.get("contact:email"),
        "website": tags.get("website") or tags.get("contact:website") or tags.get("url"),
        "address": address,
        "coordinates": [el_lon, el_lat],  # [lon, lat] padrão GeoJSON
        "osm_type": osm_type,
        "osm_id": f"{el['type']}/{el['id']}",
        "source": "openstreetmap",
        "raw_tags": tags  # Mantém tags originais para debug/filtros futuros
    }

    # Remove None
    lead = {k: v for k, v in lead.items() if v is not None}
    lead["has_whatsapp"] = has_mobile_phone(lead.get("phone", ""))
    return lead


import re

def normalize_phone(phone: str) -> str:
    """Normaliza telefone para formato DDD+número."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('55'):
        digits = digits[2:]
    return digits

def is_mobile_phone(phone: str) -> bool:
    """Verifica se telefone é celular (qualquer DDD com nono dígito: XX9XXXXXXXX)."""
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    return bool(re.match(r'^\d{2}9\d{8}$', normalized))

def has_mobile_phone(phone_field: str) -> bool:
    """Verifica se qualquer telefone no campo é celular (tem nono dígito)."""
    if not phone_field:
        return False
    for phone in re.split(r'[;,]', phone_field):
        if is_mobile_phone(phone.strip()):
            return True
    return False

def filter_leads(leads: List[dict], args) -> List[dict]:
    """Aplica filtros opcionais."""
    if args.only_with_phone:
        leads = [l for l in leads if l.get("phone")]
    if args.only_with_website:
        leads = [l for l in leads if l.get("website")]
    if args.only_whatsapp_dd21:
        leads = [l for l in leads if l.get("has_whatsapp")]
    if args.min_reviews:
        # OSM não tem reviews nativamente, mantém tudo se não tiver fonte externa
        pass
    if args.limit:
        leads = leads[:args.limit]
    return leads


def main():
    parser = argparse.ArgumentParser(description="Maps Lead Extractor - OpenStreetMap/Overpass")
    parser.add_argument("--location", help="Cidade/endereço ou 'lat,lon' (obrigatório exceto com --input)")
    parser.add_argument("--business_types", help="Tipos OSM separados por vírgula")
    parser.add_argument("--category", choices=list(CATEGORIES.keys()), help="Categoria pré-definida")
    parser.add_argument("--radius", type=int, default=5000, help="Raio em metros (padrão: 5000)")
    parser.add_argument("--limit", type=int, default=100, help="Máximo de leads (padrão: 100)")
    parser.add_argument("--output", help="Arquivo JSON de saída")
    parser.add_argument("--input", help="Arquivo JSON de entrada (em vez de buscar no OSM)")
    parser.add_argument("--min_reviews", type=int, help="Mínimo de reviews (não disponível no OSM nativo)")
    parser.add_argument("--only_with_phone", action="store_true", help="Só leads com telefone")
    parser.add_argument("--only_with_website", action="store_true", help="Só leads com website")
    parser.add_argument("--only_whatsapp_dd21", action="store_true", help="Só leads com WhatsApp válido DDD 21 (21 9xxxxxxxx)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Logs detalhados")
    args = parser.parse_args()

    # Validação condicional
    if not args.input and not args.location:
        parser.error("--location é obrigatório (exceto quando usa --input)")

    # Modo input file (filtro apenas)
    if args.input:
        if args.verbose:
            print(f"Carregando leads de: {args.input}", file=sys.stderr)
        with open(args.input, encoding="utf-8") as f:
            leads = json.load(f)
        # Filtros
        leads = filter_leads(leads, args)
        if args.verbose:
            print(f"  Leads após filtro: {len(leads)}", file=sys.stderr)
    else:
        # Modo OSM (busca + filtro)
        # Validação
        if not args.business_types and not args.category:
            parser.error("Forneça --business_types OU --category")

        # Resolve tipos
        if args.category:
            types = CATEGORIES[args.category]
            if args.verbose:
                print(f"Categoria '{args.category}': {len(types)} tipos", file=sys.stderr)
        else:
            types = [t.strip() for t in args.business_types.split(",") if t.strip()]

        # Geocodifica
        if args.verbose:
            print(f"Geocodificando: {args.location}...", file=sys.stderr)
        lat, lon = geocode(args.location)
        if args.verbose:
            print(f"  → {lat:.6f}, {lon:.6f}", file=sys.stderr)

        # Query Overpass
        if args.verbose:
            print(f"Consultando Overpass API (raio {args.radius}m, {len(types)} tipos)...", file=sys.stderr)
        query = build_overpass_query(lat, lon, types, args.radius)
        if args.verbose:
            print(f"  Query: {query[:200]}...", file=sys.stderr)

        data = query_overpass(query)
        elements = data.get("elements", [])

        if args.verbose:
            print(f"  Encontrados {len(elements)} elementos OSM", file=sys.stderr)

        # Extrai leads
        leads = []
        seen_names = set()
        for el in elements:
            lead = extract_lead_from_element(el, lat, lon)
            if lead and lead["lead_name"] not in seen_names:
                seen_names.add(lead["lead_name"])
                leads.append(lead)

        # Filtros
        leads = filter_leads(leads, args)

    if args.verbose:
        print(f"  Leads finais: {len(leads)}", file=sys.stderr)

    # Output
    output_json = json.dumps(leads, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Salvo em: {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()