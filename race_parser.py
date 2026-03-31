"""
Parser de archivos XML de resultados de carrera rFactor2.
Extrae tres tipos de eventos:
  - Tipo 1: Adelantamientos (inferidos de posiciones por vuelta)
  - Tipo 2: Choques entre pilotos (Incident con "another vehicle")
  - Tipo 3: Choques contra el muro (Incident con "Wing")
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class RaceHeader:
    track_event: str
    track_length: float      # en metros
    race_laps: int
    num_drivers: int
    grid_order: List[str]    # orden de salida (posición 1 = primero)
    intro_text: str = ""     # texto introductorio generado por IA


@dataclass
class RaceEvent:
    lap: int
    timestamp: float
    event_type: int          # 1=adelantamiento, 2=choque piloto, 3=choque muro
    summary: str             # Resumen genérico
    description: str = ""    # Descripción amigable (rellenada por IA)


def _parse_stream_incidents(xml_content: str) -> List[RaceEvent]:
    """
    Extrae eventos de incidentes del bloque <Stream>...</Stream>.
    Devuelve lista de RaceEvent tipo 2 y tipo 3.
    """
    events: List[RaceEvent] = []

    # Extraer el bloque Stream completo
    stream_match = re.search(r'<Stream>(.*?)</Stream>', xml_content, re.DOTALL)
    if not stream_match:
        return events

    stream_text = stream_match.group(1)

    # Patrón para Incident
    incident_pattern = re.compile(
        r'<Incident et="([^"]+)">([^<]+)</Incident>'
    )

    # Para deduplicar: guardamos (timestamp, piloto_a, piloto_b) ya procesados
    seen_vehicle_contacts: set = set()
    seen_wall_contacts: set = set()

    for m in incident_pattern.finditer(stream_text):
        et = float(m.group(1))
        text = m.group(2).strip()

        # Choque contra el muro: "reported contact (...) with Wing"
        wall_match = re.match(
            r'(.+?)\(\d+\) reported contact \([^)]+\) with Wing',
            text
        )
        if wall_match:
            driver = wall_match.group(1).strip()
            key = (et, driver)
            if key not in seen_wall_contacts:
                seen_wall_contacts.add(key)
                events.append(RaceEvent(
                    lap=0,  # se asignará después
                    timestamp=et,
                    event_type=3,
                    summary=f"{driver} ha chocado contra el muro"
                ))
            continue

        # Choque entre pilotos: "reported contact (...) with another vehicle X"
        vehicle_match = re.match(
            r'(.+?)\(\d+\) reported contact \([^)]+\) with another vehicle (.+?)\(\d+\)',
            text
        )
        if vehicle_match:
            driver_a = vehicle_match.group(1).strip()
            driver_b = vehicle_match.group(2).strip()

            # Ignorar si es el mismo piloto con sí mismo
            if driver_a == driver_b:
                continue

            # Deduplicar: si ya existe (et, A, B) o (et, B, A), ignorar
            key_ab = (et, driver_a, driver_b)
            key_ba = (et, driver_b, driver_a)
            if key_ab in seen_vehicle_contacts or key_ba in seen_vehicle_contacts:
                continue

            seen_vehicle_contacts.add(key_ab)
            events.append(RaceEvent(
                lap=0,
                timestamp=et,
                event_type=2,
                summary=f"{driver_a} choca con {driver_b}"
            ))

    return events


def _parse_lap_positions(xml_content: str) -> Dict[str, Dict[int, int]]:
    """
    Extrae posiciones por vuelta de cada piloto desde la sección <Driver>.
    Devuelve dict: {driver_name: {lap_num: position}}
    """
    positions: Dict[str, Dict[int, int]] = {}

    # Extraer todos los bloques <Driver>
    driver_pattern = re.compile(r'<Driver>(.*?)</Driver>', re.DOTALL)
    name_pattern = re.compile(r'<Name>([^<]+)</Name>')
    lap_pattern = re.compile(r'<Lap num="(\d+)" p="(\d+)"')

    for driver_match in driver_pattern.finditer(xml_content):
        driver_block = driver_match.group(1)
        name_m = name_pattern.search(driver_block)
        if not name_m:
            continue
        driver_name = name_m.group(1).strip()
        lap_positions: Dict[int, int] = {}
        for lap_m in lap_pattern.finditer(driver_block):
            lap_num = int(lap_m.group(1))
            pos = int(lap_m.group(2))
            lap_positions[lap_num] = pos
        if lap_positions:
            positions[driver_name] = lap_positions

    return positions


def _infer_overtakes(
    positions: Dict[str, Dict[int, int]],
    lap_et_map: Optional[Dict[int, float]] = None
) -> List[RaceEvent]:
    """
    Infiere adelantamientos comparando posiciones entre vueltas consecutivas.
    Si el piloto A estaba en posición X y el piloto B en X-1 (B delante de A),
    y en la vuelta siguiente A está en X-1 y B en X, entonces A adelantó a B.
    lap_et_map: {lap_num: et_fin_vuelta} para asignar timestamp al adelantamiento.
    """
    events: List[RaceEvent] = []

    # Recopilar todas las vueltas disponibles
    all_laps: set = set()
    for lap_dict in positions.values():
        all_laps.update(lap_dict.keys())

    if not all_laps:
        return events

    sorted_laps = sorted(all_laps)
    drivers = list(positions.keys())

    for i in range(len(sorted_laps) - 1):
        lap_curr = sorted_laps[i]
        lap_next = sorted_laps[i + 1]

        # El timestamp del adelantamiento es el et de FIN de lap_curr,
        # que ahora es lap_et_map[lap_curr] (= et cuando el líder termina lap_curr)
        ts = 0.0
        if lap_et_map:
            ts = lap_et_map.get(lap_curr, 0.0)

        # Construir mapa posición->piloto para cada vuelta
        pos_to_driver_curr: Dict[int, str] = {}
        pos_to_driver_next: Dict[int, str] = {}

        for driver in drivers:
            if lap_curr in positions[driver]:
                pos_to_driver_curr[positions[driver][lap_curr]] = driver
            if lap_next in positions[driver]:
                pos_to_driver_next[positions[driver][lap_next]] = driver

        # Comparar posiciones de cada par de pilotos
        seen_pairs: set = set()
        for driver_a in drivers:
            if lap_curr not in positions[driver_a] or lap_next not in positions[driver_a]:
                continue
            pos_a_curr = positions[driver_a][lap_curr]
            pos_a_next = positions[driver_a][lap_next]

            for driver_b in drivers:
                if driver_a == driver_b:
                    continue
                if lap_curr not in positions[driver_b] or lap_next not in positions[driver_b]:
                    continue

                pair = tuple(sorted([driver_a, driver_b]))
                if pair in seen_pairs:
                    continue

                pos_b_curr = positions[driver_b][lap_curr]
                pos_b_next = positions[driver_b][lap_next]

                # A adelanta a B: B estaba delante (menor pos) y ahora A está delante
                if pos_b_curr < pos_a_curr and pos_a_next < pos_b_next:
                    seen_pairs.add(pair)
                    events.append(RaceEvent(
                        lap=lap_curr,
                        timestamp=ts,
                        event_type=1,
                        summary=f"{driver_a} adelanta a {driver_b}"
                    ))
                # B adelanta a A
                elif pos_a_curr < pos_b_curr and pos_b_next < pos_a_next:
                    seen_pairs.add(pair)
                    events.append(RaceEvent(
                        lap=lap_curr,
                        timestamp=ts,
                        event_type=1,
                        summary=f"{driver_b} adelanta a {driver_a}"
                    ))

    return events


def _assign_laps_to_incidents(
    incidents: List[RaceEvent],
    positions: Dict[str, Dict[int, int]]
) -> List[RaceEvent]:
    """
    Asigna el número de vuelta a los incidentes basándose en el timestamp (et).
    Usa los timestamps de los <Lap> de cada piloto para determinar en qué vuelta ocurrió.
    """
    # Construir lista de (et_fin_vuelta, lap_num) global (máximo et entre todos los pilotos)
    # Cada <Lap> tiene et="X" que es el elapsed time al finalizar esa vuelta
    # Necesitamos parsear los et de los laps también
    return incidents  # Se asignará en parse_race_file con info adicional


def _assign_laps_to_incidents_with_et(
    incidents: List[RaceEvent],
    lap_start_map: Dict[int, float]
) -> List[RaceEvent]:
    """
    Asigna vuelta a incidentes usando el mapa {lap_num: et_fin_vuelta}.
    El et de <Lap num="N" p="1"> es cuando el líder termina la vuelta N.
    Vuelta N: lap_start_map[N] <= et < lap_start_map[N+1]
    Eventos con timestamp < lap_start_map[1] -> vuelta de formación (lap=0).
    """
    if not lap_start_map:
        for ev in incidents:
            ev.lap = 1
        return incidents

    # Ordenar vueltas por número de vuelta
    sorted_laps = sorted(lap_start_map.items(), key=lambda x: x[0])
    lap1_et = lap_start_map.get(1, 0.0)

    for ev in incidents:
        if ev.timestamp < lap1_et:
            ev.lap = 0
            continue
        # Buscar la vuelta N tal que lap_start_map[N] <= et < lap_start_map[N+1]
        assigned_lap = sorted_laps[-1][0]
        for i, (lap_num, et_fin) in enumerate(sorted_laps):
            if ev.timestamp < et_fin:
                # El evento ocurrió antes de que termine esta vuelta
                # Si es la primera vuelta en el mapa, asignar vuelta de formación
                assigned_lap = sorted_laps[i - 1][0] if i > 0 else 0
                break
        ev.lap = assigned_lap

    return incidents


def _deduplicate_nearby_events(events: List[RaceEvent], min_gap: float = 7.0) -> List[RaceEvent]:
    """
    Elimina eventos duplicados cercanos en tiempo: si dos eventos del mismo tipo
    involucran a los mismos pilotos/piloto y su diferencia de timestamp es < min_gap
    segundos, se conserva solo el primero.
    """
    result: List[RaceEvent] = []
    # Guardamos los eventos ya aceptados para comparar
    # Clave: (event_type, frozenset de pilotos involucrados) -> último timestamp aceptado
    last_seen: Dict[Tuple, float] = {}

    for ev in events:
        # Extraer pilotos del summary para construir la clave
        if ev.event_type == 1:
            # "X adelanta a Y"
            m = re.match(r'(.+) adelanta a (.+)', ev.summary)
            if m:
                key = (ev.event_type, frozenset([m.group(1).strip(), m.group(2).strip()]))
            else:
                key = (ev.event_type, ev.summary)
        elif ev.event_type == 2:
            # "X choca con Y"
            m = re.match(r'(.+) choca con (.+)', ev.summary)
            if m:
                key = (ev.event_type, frozenset([m.group(1).strip(), m.group(2).strip()]))
            else:
                key = (ev.event_type, ev.summary)
        elif ev.event_type == 3:
            # "X ha chocado contra el muro"
            m = re.match(r'(.+) ha chocado contra el muro', ev.summary)
            if m:
                key = (ev.event_type, m.group(1).strip())
            else:
                key = (ev.event_type, ev.summary)
        else:
            key = (ev.event_type, ev.summary)

        last_ts = last_seen.get(key)
        if last_ts is None or (ev.timestamp - last_ts) >= min_gap:
            last_seen[key] = ev.timestamp
            result.append(ev)
        # Si la diferencia es < min_gap, se descarta el evento

    return result


def parse_race_file(xml_content: str) -> List[RaceEvent]:
    """
    Función principal. Parsea el contenido XML y devuelve lista de RaceEvent
    ordenados por vuelta y tipo de evento.
    """
    # 1. Extraer incidentes del Stream
    incidents = _parse_stream_incidents(xml_content)

    # 2. Extraer posiciones por vuelta
    positions = _parse_lap_positions(xml_content)

    # 3. Construir mapa {lap_num: et_inicio_vuelta} usando el et del piloto en p=1 en cada vuelta
    # El et de <Lap num="N" p="1"> es el timestamp en que el líder TERMINA la vuelta N,
    # es decir, el INICIO de la vuelta N+1. Por tanto:
    #   inicio_vuelta_1 = et de <Lap num="1" p="1">  (el líder cruza la línea de salida/meta)
    #   inicio_vuelta_N = et de <Lap num="N-1" p="1"> para N > 1
    # Primero recogemos el et de cada vuelta del líder (p=1)
    lap_end_map: Dict[int, float] = {}  # {lap_num: et_fin_vuelta (= inicio siguiente)}
    driver_pattern = re.compile(r'<Driver>(.*?)</Driver>', re.DOTALL)
    lap_full_pattern = re.compile(r'<Lap num="(\d+)" p="(\d+)" et="([^"]+)"')

    for driver_match in driver_pattern.finditer(xml_content):
        driver_block = driver_match.group(1)
        for lap_m in lap_full_pattern.finditer(driver_block):
            lap_num = int(lap_m.group(1))
            pos = int(lap_m.group(2))
            et = float(lap_m.group(3))
            if pos == 1:
                lap_end_map[lap_num] = et

    # lap_start_map: inicio de vuelta N
    # El et de <Lap num="N" p="1"> es cuando el líder TERMINA la vuelta N.
    # Por tanto, la vuelta N empieza en lap_end_map[N] (cuando el líder termina la vuelta N).
    # Todo lo anterior a lap_end_map[1] es "Vuelta de formación" (lap=0).
    # Vuelta N: lap_end_map[N] <= et < lap_end_map[N+1]
    lap_start_map: Dict[int, float] = {}
    if lap_end_map:
        for lap_num, et_fin in lap_end_map.items():
            lap_start_map[lap_num] = et_fin

    # 4. Asignar vueltas a incidentes usando et de inicio de cada vuelta
    incidents = _assign_laps_to_incidents_with_et(incidents, lap_start_map)

    # 5. Inferir adelantamientos (pasamos el mapa et para asignar timestamps)
    overtakes = _infer_overtakes(positions, lap_start_map)

    # 6. Combinar todos los eventos
    all_events = incidents + overtakes

    # 7. Ordenar por vuelta y tipo de evento
    all_events.sort(key=lambda e: (e.lap, e.event_type, e.timestamp))

    # 8. Deduplicar eventos cercanos en tiempo (< 7 segundos, mismo tipo y mismos pilotos)
    all_events = _deduplicate_nearby_events(all_events, min_gap=7.0)

    return all_events


def parse_race_header(xml_content: str) -> RaceHeader:
    """
    Extrae la información de cabecera de la carrera:
    - Nombre del circuito (<TrackEvent>)
    - Longitud del circuito en metros (<TrackLength>)
    - Número de vueltas (<RaceLaps>)
    - Número de pilotos y orden de salida (primeras <Score> con point=1 del Stream)
    """
    # Nombre del circuito
    track_event_m = re.search(r'<TrackEvent>([^<]+)</TrackEvent>', xml_content)
    track_event = track_event_m.group(1).strip().replace("_", " ") if track_event_m else "Desconocido"

    # Longitud del circuito
    track_length_m = re.search(r'<TrackLength>([^<]+)</TrackLength>', xml_content)
    track_length = float(track_length_m.group(1).strip()) if track_length_m else 0.0

    # Número de vueltas
    race_laps_m = re.search(r'<RaceLaps>([^<]+)</RaceLaps>', xml_content)
    race_laps = int(race_laps_m.group(1).strip()) if race_laps_m else 0

    # Orden de salida: las primeras Score con point=1 en el Stream (una por piloto)
    stream_match = re.search(r'<Stream>(.*?)</Stream>', xml_content, re.DOTALL)
    grid_order: List[str] = []
    if stream_match:
        stream_text = stream_match.group(1)
        score_pattern = re.compile(
            r'<Score[^>]*>([^<(]+)\(\d+\) lap=0 point=1[^<]*</Score>'
        )
        seen_drivers: set = set()
        for sm in score_pattern.finditer(stream_text):
            driver = sm.group(1).strip()
            if driver not in seen_drivers:
                seen_drivers.add(driver)
                grid_order.append(driver)

    return RaceHeader(
        track_event=track_event,
        track_length=track_length,
        race_laps=race_laps,
        num_drivers=len(grid_order),
        grid_order=grid_order,
    )


def generate_ai_intro(header: RaceHeader, ollama_url: str, ollama_model: str) -> RaceHeader:
    """
    Genera un texto introductorio de la carrera usando Ollama,
    como si fuera un comentarista de Fórmula 1.
    """
    import requests as req

    # Construir descripción de parrilla: apreciación graciosa para los 3 primeros, solo posición para el resto
    top3 = header.grid_order[:3]
    rest = header.grid_order[3:]
    top3_str = ", ".join(f"{i+1}. {name}" for i, name in enumerate(top3))
    rest_str = ", ".join(f"{i+4}. {name}" for i, name in enumerate(rest))
    grid_section = f"Los tres primeros en parrilla son: {top3_str}."
    if rest_str:
        grid_section += f" El resto de pilotos salen en estas posiciones: {rest_str}."

    prompt = (
        f"Eres el comentarista oficial de una carrera de Fórmula 1. "
        f"Presenta la carrera de forma emocionante y natural. "
        f"La carrera se celebra en el circuito '{header.track_event}', "
        f"con una longitud de {header.track_length:.0f} metros por vuelta, "
        f"a lo largo de {header.race_laps} vueltas. "
        f"Participan {header.num_drivers} pilotos. "
        f"{grid_section} "
        f"Narra la parrilla de salida empezando por el primero. "
        f"Para los 3 primeros pilotos ({top3_str}), haz una apreciación graciosa y positiva (en tono de broma amigable) sobre cada uno. "
        f"Para el resto de pilotos, menciona únicamente su posición de salida. "
        f"Responde SOLO con el texto de presentación, sin títulos ni explicaciones adicionales."
    )

    try:
        response = req.post(
            f"{ollama_url}/api/generate",
            json={
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.85, "top_p": 0.95, "seed": 42}
            },
            timeout=60
        )
        if response.status_code == 200:
            header.intro_text = response.json().get("response", "").strip().strip('"\'')
        else:
            header.intro_text = ""
    except Exception:
        header.intro_text = ""

    return header


def generate_ai_descriptions(events: List[RaceEvent], ollama_url: str, ollama_model: str) -> List[RaceEvent]:
    """
    Genera descripciones amigables para cada evento usando Ollama.
    Las descripciones deben ser variadas y no repetirse.
    """
    import requests as req

    used_descriptions: List[str] = []

    for i, event in enumerate(events):
        type_hints = {
            1: "adelantamiento en carrera de Fórmula 1",
            2: "choque o contacto entre dos pilotos en carrera de Fórmula 1",
            3: "choque de un piloto contra el muro o barrera en carrera de Fórmula 1"
        }

        avoid_hint = ""
        if used_descriptions:
            last_few = used_descriptions[-5:]
            avoid_hint = f"\nEvita usar frases similares a estas descripciones anteriores: {'; '.join(last_few)}"

        # Contexto de adelantamientos previos del piloto (solo para Tipo 1)
        overtake_hint = ""
        if event.event_type == 1:
            driver_a = event.summary.split(" adelanta a ")[0] if " adelanta a " in event.summary else ""
            if driver_a:
                prev_overtakes = sum(
                    1 for e in events[:i]
                    if e.event_type == 1 and " adelanta a " in e.summary and e.summary.startswith(driver_a)
                )
                if prev_overtakes >= 3:
                    overtake_hint = f" Menciona que este piloto ya lleva {prev_overtakes} adelantamientos en la carrera."

        prompt = (
            f"Eres un comentarista deportivo de Fórmula 1 apasionado y dinámico. "
            f"Genera UNA SOLA frase corta (máximo 25 palabras) y emocionante describiendo este evento de {type_hints.get(event.event_type, 'carrera')}: "
            f"'{event.summary}' en la vuelta {event.lap}. "
            f"La descripción debe ser variada, natural y diferente a las anteriores.{overtake_hint} "
            f"Responde SOLO con la frase, sin comillas ni explicaciones adicionales.{avoid_hint}"
        )

        try:
            response = req.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.9,
                        "top_p": 0.95,
                        "seed": i * 37 + 13  # seed diferente para cada evento
                    }
                },
                timeout=30
            )
            if response.status_code == 200:
                description = response.json().get("response", "").strip()
                # Limpiar comillas si las hay
                description = description.strip('"\'')
                event.description = description
                used_descriptions.append(description)
            else:
                event.description = event.summary
        except Exception:
            event.description = event.summary

    return events
