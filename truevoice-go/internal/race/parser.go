package race

import (
	"encoding/json"
	"fmt"
	"math"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// ── Data Structures ────────────────────────────────────────────────

type RaceHeader struct {
	TrackEvent  string   `json:"track_event"`
	TrackLength float64  `json:"track_length"`
	RaceLaps    int      `json:"race_laps"`
	NumDrivers  int      `json:"num_drivers"`
	GridOrder   []string `json:"grid_order"`
	IntroText   string   `json:"intro_text"`
}

type RaceEvent struct {
	Lap         int     `json:"lap"`
	Timestamp   float64 `json:"timestamp"`
	EventType   int     `json:"event_type"` // 1=overtake 2=driver collision 3=wall 4=penalty 5=pit
	Summary     string  `json:"summary"`
	Description string  `json:"description"`
}

type RaceSession struct {
	IntroText   string            `json:"intro_text"`
	IntroAudio  string            `json:"intro_audio"`
	Header      RaceHeader        `json:"header"`
	Events      []RaceEvent       `json:"events"`
	EventAudios map[string]string `json:"event_audios"`
}

// ── Regexes ────────────────────────────────────────────────────────

var (
	reIncident      = regexp.MustCompile(`<Incident et="([^"]+)">([^<]+)</Incident>`)
	rePenalty        = regexp.MustCompile(`<Penalty et="([^"]+)">([^<]+)</Penalty>`)
	reWallContact    = regexp.MustCompile(`(.+?)\(\d+\) reported contact \([^)]+\) with Wing`)
	reVehicleContact = regexp.MustCompile(`(.+?)\(\d+\) reported contact \([^)]+\) with another vehicle (.+?)\(\d+\)`)
	reDriver         = regexp.MustCompile(`(?s)<Driver>(.*?)</Driver>`)
	reName           = regexp.MustCompile(`<Name>([^<]+)</Name>`)
	reGridPos        = regexp.MustCompile(`<GridPos>(\d+)</GridPos>`)
	reLapTag         = regexp.MustCompile(`(<Lap\s+num="(\d+)"\s+p="(\d+)"\s+et="([^"]+)"[^>]*>.*?</Lap>)`)
	reStream         = regexp.MustCompile(`(?s)<Stream>(.*?)</Stream>`)
	reTrackEvent     = regexp.MustCompile(`<TrackEvent>([^<]+)</TrackEvent>`)
	reTrackLength    = regexp.MustCompile(`<TrackLength>([^<]+)</TrackLength>`)
	reRaceLaps       = regexp.MustCompile(`<RaceLaps>([^<]+)</RaceLaps>`)
	reScoreGrid      = regexp.MustCompile(`<Score[^>]*>([^<(]+)\(\d+\) lap=0 point=1[^<]*</Score>`)
	reAdelanta       = regexp.MustCompile(`(.+) adelanta a (.+)`)
	reChoca          = regexp.MustCompile(`(.+) choca con (.+)`)
	reMuro           = regexp.MustCompile(`(.+) ha chocado contra el muro`)
	reReceived       = regexp.MustCompile(`(.+?) received`)
)

// ── Parse Stream Incidents ─────────────────────────────────────────

func parseStreamIncidents(xml string) []RaceEvent {
	var events []RaceEvent
	streamMatch := reStream.FindStringSubmatch(xml)
	if len(streamMatch) < 2 {
		return events
	}
	streamText := streamMatch[1]

	// Collision dedup sets
	type contactKey struct{ et float64; a, b string }
	type wallKey struct{ et float64; driver string }
	seenVehicle := map[contactKey]bool{}
	seenWall := map[wallKey]bool{}

	for _, m := range reIncident.FindAllStringSubmatch(streamText, -1) {
		et := parseFloat(m[1])
		text := strings.TrimSpace(m[2])

		// Wall collision
		if wm := reWallContact.FindStringSubmatch(text); len(wm) > 0 {
			driver := strings.TrimSpace(wm[1])
			key := wallKey{et, driver}
			if !seenWall[key] {
				seenWall[key] = true
				events = append(events, RaceEvent{
					Timestamp: et, EventType: 3,
					Summary: fmt.Sprintf("%s ha chocado contra el muro", driver),
				})
			}
			continue
		}

		// Vehicle collision
		if vm := reVehicleContact.FindStringSubmatch(text); len(vm) > 0 {
			a := strings.TrimSpace(vm[1])
			b := strings.TrimSpace(vm[2])
			if a == b {
				continue
			}
			keyAB := contactKey{et, a, b}
			keyBA := contactKey{et, b, a}
			if !seenVehicle[keyAB] && !seenVehicle[keyBA] {
				seenVehicle[keyAB] = true
				events = append(events, RaceEvent{
					Timestamp: et, EventType: 2,
					Summary: fmt.Sprintf("%s choca con %s", a, b),
				})
			}
		}
	}

	// Penalties
	for _, m := range rePenalty.FindAllStringSubmatch(streamText, -1) {
		et := parseFloat(m[1])
		text := strings.TrimSpace(m[2])

		if !strings.Contains(text, "Stop/Go") && !strings.Contains(text, "Drive Thru") {
			continue
		}
		typeStr := "Drive Through"
		if strings.Contains(text, "Stop/Go") {
			typeStr = "STOP and GO"
		}
		if strings.Contains(text, "received") {
			driver := "Piloto desconocido"
			if pm := reReceived.FindStringSubmatch(text); len(pm) > 0 {
				driver = strings.TrimSpace(pm[1])
			}
			events = append(events, RaceEvent{
				Timestamp: et, EventType: 4,
				Summary: fmt.Sprintf("%s recibida para %s", typeStr, driver),
			})
		}
	}

	return events
}

// ── Parse Lap Positions ────────────────────────────────────────────

func parseLapPositions(xml string) map[string]map[int]int {
	positions := make(map[string]map[int]int)

	for _, dm := range reDriver.FindAllStringSubmatch(xml, -1) {
		block := dm[1]
		nm := reName.FindStringSubmatch(block)
		if nm == nil {
			continue
		}
		name := strings.TrimSpace(nm[1])
		laps := make(map[int]int)

		if gm := reGridPos.FindStringSubmatch(block); gm != nil {
			laps[0] = parseInt(gm[1])
		}

		reLap := regexp.MustCompile(`<Lap num="(\d+)" p="(\d+)"`)
		for _, lm := range reLap.FindAllStringSubmatch(block, -1) {
			lapNum := parseInt(lm[1])
			pos := parseInt(lm[2])
			laps[lapNum] = pos
		}
		if len(laps) > 0 {
			positions[name] = laps
		}
	}
	return positions
}

// ── Infer Overtakes ────────────────────────────────────────────────

func inferOvertakes(positions map[string]map[int]int, lapETMap map[int]float64) []RaceEvent {
	var events []RaceEvent

	allLaps := map[int]bool{}
	for _, lm := range positions {
		for l := range lm {
			allLaps[l] = true
		}
	}
	sortedLaps := make([]int, 0, len(allLaps))
	for l := range allLaps {
		sortedLaps = append(sortedLaps, l)
	}
	sort.Ints(sortedLaps)

	drivers := make([]string, 0, len(positions))
	for d := range positions {
		drivers = append(drivers, d)
	}

	type pair struct{ a, b string }

	for i := 0; i < len(sortedLaps)-1; i++ {
		curr := sortedLaps[i]
		next := sortedLaps[i+1]
		ts := lapETMap[next]

		seen := map[pair]bool{}

		for _, driverA := range drivers {
			posACurr, okAC := positions[driverA][curr]
			posANext, okAN := positions[driverA][next]
			if !okAC || !okAN {
				continue
			}

			for _, driverB := range drivers {
				if driverA == driverB {
					continue
				}

				// Normalize pair
				p := pair{driverA, driverB}
				if driverA > driverB {
					p = pair{driverB, driverA}
				}
				if seen[p] {
					continue
				}

				posBCurr, okBC := positions[driverB][curr]
				posBNext, okBN := positions[driverB][next]
				if !okBC || !okBN {
					continue
				}

				if posBCurr < posACurr && posANext < posBNext {
					seen[p] = true
					events = append(events, RaceEvent{
						Lap: next, Timestamp: ts, EventType: 1,
						Summary: fmt.Sprintf("%s adelanta a %s", driverA, driverB),
					})
				} else if posACurr < posBCurr && posBNext < posANext {
					seen[p] = true
					events = append(events, RaceEvent{
						Lap: next, Timestamp: ts, EventType: 1,
						Summary: fmt.Sprintf("%s adelanta a %s", driverB, driverA),
					})
				}
			}
		}
	}
	return events
}

// ── Assign Laps to Incidents ───────────────────────────────────────

func assignLaps(events []RaceEvent, lapStartMap map[int]float64) []RaceEvent {
	if len(lapStartMap) == 0 {
		for i := range events {
			events[i].Lap = 1
		}
		return events
	}

	type lapEntry struct {
		num int
		et  float64
	}
	sorted := make([]lapEntry, 0, len(lapStartMap))
	for n, et := range lapStartMap {
		sorted = append(sorted, lapEntry{n, et})
	}
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].num < sorted[j].num })

	for i := range events {
		if events[i].Timestamp < sorted[0].et {
			events[i].Lap = 0
			continue
		}
		assigned := sorted[0].num
		for _, le := range sorted {
			if events[i].Timestamp >= le.et {
				assigned = le.num
			} else {
				break
			}
		}
		events[i].Lap = assigned
	}
	return events
}

// ── Deduplicate Nearby Events ──────────────────────────────────────

func deduplicateNearby(events []RaceEvent, minGap float64) []RaceEvent {
	type dedupKey struct {
		eventType int
		actors    string
	}

	extractKey := func(ev RaceEvent) dedupKey {
		switch ev.EventType {
		case 1:
			if m := reAdelanta.FindStringSubmatch(ev.Summary); m != nil {
				actors := sortedPair(strings.TrimSpace(m[1]), strings.TrimSpace(m[2]))
				return dedupKey{ev.EventType, actors}
			}
		case 2:
			if m := reChoca.FindStringSubmatch(ev.Summary); m != nil {
				actors := sortedPair(strings.TrimSpace(m[1]), strings.TrimSpace(m[2]))
				return dedupKey{ev.EventType, actors}
			}
		case 3:
			if m := reMuro.FindStringSubmatch(ev.Summary); m != nil {
				return dedupKey{ev.EventType, strings.TrimSpace(m[1])}
			}
		}
		return dedupKey{ev.EventType, ev.Summary}
	}

	lastSeen := map[dedupKey]float64{}
	var result []RaceEvent

	for _, ev := range events {
		key := extractKey(ev)
		if last, ok := lastSeen[key]; ok && (ev.Timestamp-last) < minGap {
			continue
		}
		lastSeen[key] = ev.Timestamp
		result = append(result, ev)
	}
	return result
}

// ── Main Parse Functions ───────────────────────────────────────────

func ParseRaceFile(xml string) []RaceEvent {
	// 1. Incidents from Stream
	incidents := parseStreamIncidents(xml)

	// 2. Positions
	positions := parseLapPositions(xml)
	var pitStops []RaceEvent

	// 3. Build lap_start_map
	lapStartMap := map[int]float64{}
	var gridPos1Driver string
	lapP1Drivers := map[int]string{}
	driverLapsET := map[string]map[int]float64{}

	for _, dm := range reDriver.FindAllStringSubmatch(xml, -1) {
		block := dm[1]
		nm := reName.FindStringSubmatch(block)
		if nm == nil {
			continue
		}
		dName := strings.TrimSpace(nm[1])

		if gm := reGridPos.FindStringSubmatch(block); gm != nil && parseInt(gm[1]) == 1 {
			gridPos1Driver = dName
		}

		dETMap := map[int]float64{}
		var lapsWithPit []int

		for _, lm := range reLapTag.FindAllStringSubmatch(block, -1) {
			fullLine := lm[1]
			ln := parseInt(lm[2])
			lp := parseInt(lm[3])
			let := parseFloat(lm[4])

			dETMap[ln] = let
			if lp == 1 {
				lapP1Drivers[ln] = dName
			}
			if strings.Contains(strings.ToLower(fullLine), "pit") {
				lapsWithPit = append(lapsWithPit, ln)
			}
		}

		// Pit stops
		for _, lnPit := range lapsWithPit {
			reNextLap := regexp.MustCompile(fmt.Sprintf(`<Lap num="%d"[^>]+et="([^"]+)"`, lnPit+1))
			if nextM := reNextLap.FindStringSubmatch(block); nextM != nil {
				pitTS := parseFloat(nextM[1])
				pitStops = append(pitStops, RaceEvent{
					Lap: 1, Timestamp: pitTS, EventType: 5,
					Summary: fmt.Sprintf("%s entra en boxes", dName),
				})
			} else if et, ok := dETMap[lnPit]; ok {
				pitStops = append(pitStops, RaceEvent{
					Lap: 1, Timestamp: et, EventType: 5,
					Summary: fmt.Sprintf("%s entra en boxes", dName),
				})
			}
		}
		driverLapsET[dName] = dETMap
	}

	// Lap start map
	if gridPos1Driver != "" {
		if etMap, ok := driverLapsET[gridPos1Driver]; ok {
			if et1, ok := etMap[1]; ok {
				lapStartMap[1] = et1
			}
		}
	}
	maxLap := 0
	for ln := range lapP1Drivers {
		if ln > maxLap {
			maxLap = ln
		}
	}
	for ln := 2; ln <= maxLap; ln++ {
		if prevLeader, ok := lapP1Drivers[ln-1]; ok {
			if etMap, ok := driverLapsET[prevLeader]; ok {
				if et, ok := etMap[ln]; ok {
					lapStartMap[ln] = et
					continue
				}
			}
		}
		if currLeader, ok := lapP1Drivers[ln]; ok {
			if etMap, ok := driverLapsET[currLeader]; ok {
				if et, ok := etMap[ln]; ok {
					lapStartMap[ln] = et
				}
			}
		}
	}

	// 4. Assign laps
	incidents = assignLaps(incidents, lapStartMap)
	pitStops = assignLaps(pitStops, lapStartMap)

	// 5. Overtakes
	overtakes := inferOvertakes(positions, lapStartMap)

	// 6. Combine
	allEvents := make([]RaceEvent, 0, len(incidents)+len(overtakes)+len(pitStops))
	allEvents = append(allEvents, incidents...)
	allEvents = append(allEvents, overtakes...)
	allEvents = append(allEvents, pitStops...)

	// 7. Sort
	sort.Slice(allEvents, func(i, j int) bool {
		if allEvents[i].Lap != allEvents[j].Lap {
			return allEvents[i].Lap < allEvents[j].Lap
		}
		if allEvents[i].EventType != allEvents[j].EventType {
			return allEvents[i].EventType < allEvents[j].EventType
		}
		return allEvents[i].Timestamp < allEvents[j].Timestamp
	})

	// 8. Deduplicate
	allEvents = deduplicateNearby(allEvents, 7.0)

	return allEvents
}

func ParseRaceHeader(xml string) RaceHeader {
	trackEvent := "Desconocido"
	if m := reTrackEvent.FindStringSubmatch(xml); m != nil {
		trackEvent = strings.ReplaceAll(strings.TrimSpace(m[1]), "_", " ")
	}

	var trackLength float64
	if m := reTrackLength.FindStringSubmatch(xml); m != nil {
		trackLength = parseFloat(strings.TrimSpace(m[1]))
	}

	var raceLaps int
	if m := reRaceLaps.FindStringSubmatch(xml); m != nil {
		raceLaps = parseInt(strings.TrimSpace(m[1]))
	}

	var gridOrder []string
	if sm := reStream.FindStringSubmatch(xml); len(sm) > 1 {
		seen := map[string]bool{}
		for _, m := range reScoreGrid.FindAllStringSubmatch(sm[1], -1) {
			driver := strings.TrimSpace(m[1])
			if !seen[driver] {
				seen[driver] = true
				gridOrder = append(gridOrder, driver)
			}
		}
	}

	return RaceHeader{
		TrackEvent:  trackEvent,
		TrackLength: trackLength,
		RaceLaps:    raceLaps,
		NumDrivers:  len(gridOrder),
		GridOrder:   gridOrder,
	}
}

// ── Helpers ────────────────────────────────────────────────────────

func parseFloat(s string) float64 {
	f, _ := strconv.ParseFloat(strings.TrimSpace(s), 64)
	return f
}

func parseInt(s string) int {
	i, _ := strconv.Atoi(strings.TrimSpace(s))
	return i
}

func sortedPair(a, b string) string {
	if a > b {
		a, b = b, a
	}
	return a + "|" + b
}

// MarshalRaceSession serializes a session to JSON.
func MarshalRaceSession(s RaceSession) ([]byte, error) {
	return json.MarshalIndent(s, "", "  ")
}

// UnmarshalRaceSession deserializes session JSON.
func UnmarshalRaceSession(data []byte) (RaceSession, error) {
	var s RaceSession
	err := json.Unmarshal(data, &s)
	return s, err
}

// ── Unused but mirrors Python API ──────────────────────────────────

var _ = math.Abs // keep math import
