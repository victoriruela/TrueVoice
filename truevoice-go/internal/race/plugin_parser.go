package race

import (
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strings"
)

// ── JSON structures produced by the rF2 TrueVoice plugin ──────────

type pluginJSON struct {
	// Current C++ writer schema (top-level fields)
	TrackName   string `json:"track_name"`
	TrackLength float64 `json:"track_length"`
	SessionType string `json:"session_type"`
	NumLaps     int `json:"num_laps"`
	Drivers     []struct {
		Name    string `json:"name"`
		GridPos int    `json:"grid_pos"`
	} `json:"drivers"`

	// Backward compatibility schema (nested header)
	Header struct {
		TrackName   string  `json:"track_name"`
		TrackLength float64 `json:"track_length"`
		SessionType string  `json:"session_type"`
		NumVehicles int     `json:"num_vehicles"`
	} `json:"header"`
	GridOrder []struct {
		Name  string `json:"name"`
		Place int    `json:"place"`
	} `json:"grid_order"`

	Events []pluginEvent `json:"events"`
}

type pluginEvent struct {
	Type string `json:"type"`

	// Current C++ writer keys
	TimestampET     float64  `json:"timestamp_et"`
	TimestampHMS    string   `json:"timestamp_hms"`
	Lap             int      `json:"lap"`
	LapDist         float64  `json:"lap_dist"`
	DriversInvolved []string `json:"drivers_involved"`
	ImpactMagnitude float64  `json:"impact_magnitude,omitempty"`
	GapSeconds      float64  `json:"gap_seconds,omitempty"`
	NewPositions    map[string]int `json:"new_positions,omitempty"`
	PenaltyCount    int      `json:"penalty_count,omitempty"`
	PitReason       string   `json:"pit_reason,omitempty"`
	LapTime         float64  `json:"lap_time,omitempty"`
	LapTimeHMS      string   `json:"lap_time_hms,omitempty"`
	SurfaceType     string   `json:"surface_type,omitempty"`
	PenaltyServed   bool     `json:"penalty_served,omitempty"`
	TiresRemoved    struct {
		Front string `json:"front"`
		Rear  string `json:"rear"`
	} `json:"tires_removed,omitempty"`
	TiresInstalled struct {
		Front string `json:"front"`
		Rear  string `json:"rear"`
	} `json:"tires_installed,omitempty"`

	// Legacy keys kept for compatibility
	Timestamp float64 `json:"timestamp,omitempty"`
	Driver    string  `json:"driver,omitempty"`
	Other     string  `json:"other,omitempty"`
	Summary   string  `json:"summary,omitempty"`
	Magnitude    float64 `json:"magnitude,omitempty"`
	NewPlace     int     `json:"new_place,omitempty"`
	OldPlace     int     `json:"old_place,omitempty"`
	BestLapTime  float64 `json:"best_lap_time,omitempty"`
	Gap          float64 `json:"gap,omitempty"`
	NumWheelsOff int     `json:"num_wheels_off,omitempty"`
	Reason       string  `json:"reason,omitempty"`
	TireFront    string  `json:"tire_front,omitempty"`
	TireRear     string  `json:"tire_rear,omitempty"`

	Position struct {
		X float64 `json:"x"`
		Y float64 `json:"y"`
		Z float64 `json:"z"`
	} `json:"position"`
	DriverPositions []struct {
		Name    string `json:"name"`
		Place   int    `json:"place"`
		Pos     struct {
			X float64 `json:"x"`
			Y float64 `json:"y"`
			Z float64 `json:"z"`
		} `json:"pos"`
		LapDist float64 `json:"lap_dist"`
		Lap     int     `json:"lap"`
	} `json:"driver_positions,omitempty"`
}

var pluginTypeToEventType = map[string]int{
	"overtake":          1,
	"collision_vehicle": 2,
	"collision_wall":    3,
	"penalty":           4,
	"pit_entry":         5,
	"off_track":         6,
	"proximity":         7,
	"fastest_lap":       8,
}

func ParsePluginJSON(data []byte) (RaceHeader, []RaceEvent, error) {
	var pj pluginJSON
	if err := json.Unmarshal(data, &pj); err != nil {
		return RaceHeader{}, nil, fmt.Errorf("invalid plugin JSON: %w", err)
	}

	trackName := strings.TrimSpace(pj.TrackName)
	if trackName == "" {
		trackName = strings.TrimSpace(pj.Header.TrackName)
	}
	trackLength := pj.TrackLength
	if trackLength <= 0 {
		trackLength = pj.Header.TrackLength
	}
	numDrivers := len(pj.Drivers)
	if numDrivers == 0 {
		numDrivers = pj.Header.NumVehicles
	}
	raceLaps := pj.NumLaps

	grid := buildGridOrder(pj)

	if raceLaps <= 0 {
		for _, ev := range pj.Events {
			if ev.Lap > raceLaps {
				raceLaps = ev.Lap
			}
		}
	}

	header := RaceHeader{
		TrackEvent:  trackName,
		TrackLength: trackLength,
		RaceLaps:    raceLaps,
		NumDrivers:  numDrivers,
		GridOrder:   grid,
	}

	events := make([]RaceEvent, 0, len(pj.Events))
	for _, pe := range pj.Events {
		evType, ok := pluginTypeToEventType[pe.Type]
		if !ok {
			continue
		}

		timestamp := pe.TimestampET
		if timestamp == 0 {
			timestamp = pe.Timestamp
		}

		re := RaceEvent{
			Lap:       pe.Lap,
			Timestamp: timestamp,
			EventType: evType,
			Summary:   pluginSummary(pe),
			Position: &EventPosition{
				X: pe.Position.X,
				Y: pe.Position.Y,
				Z: pe.Position.Z,
			},
		}

		if len(pe.DriverPositions) > 0 {
			snaps := make([]DriverSnapshot, len(pe.DriverPositions))
			for i, d := range pe.DriverPositions {
				snaps[i] = DriverSnapshot{
					Name:    d.Name,
					Place:   d.Place,
					Pos:     EventPosition{X: d.Pos.X, Y: d.Pos.Y, Z: d.Pos.Z},
					LapDist: d.LapDist,
					Lap:     d.Lap,
				}
			}
			re.DriverPositions = snaps
		}

		extra := map[string]any{}
		switch pe.Type {
		case "collision_vehicle", "collision_wall":
			mag := pe.ImpactMagnitude
			if mag == 0 {
				mag = pe.Magnitude
			}
			extra["magnitude"] = mag
		case "overtake":
			if len(pe.NewPositions) > 0 {
				extra["new_positions"] = pe.NewPositions
			}
			if pe.NewPlace != 0 || pe.OldPlace != 0 {
				extra["new_place"] = pe.NewPlace
				extra["old_place"] = pe.OldPlace
			}
		case "proximity":
			gap := pe.GapSeconds
			if gap == 0 {
				gap = pe.Gap
			}
			extra["gap"] = gap
		case "off_track":
			if pe.NumWheelsOff != 0 {
				extra["num_wheels_off"] = pe.NumWheelsOff
			}
			if pe.SurfaceType != "" {
				extra["surface_type"] = pe.SurfaceType
			}
		case "pit_entry":
			reason := firstNonEmpty(pe.PitReason, pe.Reason)
			if reason != "" {
				extra["reason"] = reason
			}
			front := firstNonEmpty(pe.TiresInstalled.Front, pe.TireFront)
			rear := firstNonEmpty(pe.TiresInstalled.Rear, pe.TireRear)
			if front != "" {
				extra["tire_front"] = front
			}
			if rear != "" {
				extra["tire_rear"] = rear
			}
			extra["penalty_served"] = pe.PenaltyServed
		case "penalty":
			extra["penalty_count"] = pe.PenaltyCount
		case "fastest_lap":
			lapTime := pe.LapTime
			if lapTime == 0 {
				lapTime = pe.BestLapTime
			}
			extra["best_lap_time"] = lapTime
			if pe.LapTimeHMS != "" {
				extra["best_lap_hms"] = pe.LapTimeHMS
			}
		}
		if len(extra) > 0 {
			re.ExtraData = extra
		}

		events = append(events, re)
	}

	sort.SliceStable(events, func(i, j int) bool {
		return events[i].Timestamp < events[j].Timestamp
	})

	return header, events, nil
}

func buildGridOrder(pj pluginJSON) []string {
	type gridEntry struct {
		Name  string
		Place int
	}

	entries := make([]gridEntry, 0)
	for _, d := range pj.Drivers {
		if strings.TrimSpace(d.Name) == "" {
			continue
		}
		entries = append(entries, gridEntry{Name: d.Name, Place: d.GridPos})
	}
	for _, g := range pj.GridOrder {
		if strings.TrimSpace(g.Name) == "" {
			continue
		}
		entries = append(entries, gridEntry{Name: g.Name, Place: g.Place})
	}

	sort.SliceStable(entries, func(i, j int) bool {
		pi, pj := entries[i].Place, entries[j].Place
		if pi <= 0 && pj <= 0 {
			return i < j
		}
		if pi <= 0 {
			return false
		}
		if pj <= 0 {
			return true
		}
		return pi < pj
	})

	out := make([]string, 0, len(entries))
	seen := map[string]bool{}
	for _, e := range entries {
		name := strings.TrimSpace(e.Name)
		if name == "" || seen[name] {
			continue
		}
		seen[name] = true
		out = append(out, name)
	}
	return out
}

func pluginSummary(pe pluginEvent) string {
	timestamp := pe.TimestampET
	if timestamp == 0 {
		timestamp = pe.Timestamp
	}
	ts := formatTimestamp(timestamp)
	driver, other := resolveDrivers(pe)

	switch pe.Type {
	case "collision_vehicle":
		mag := pe.ImpactMagnitude
		if mag == 0 {
			mag = pe.Magnitude
		}
		return fmt.Sprintf("Vuelta %d [%s]: Colision entre %s y %s (fuerza %.0f)", pe.Lap, ts, driver, other, mag)
	case "collision_wall":
		mag := pe.ImpactMagnitude
		if mag == 0 {
			mag = pe.Magnitude
		}
		return fmt.Sprintf("Vuelta %d [%s]: %s choca contra el muro (fuerza %.0f)", pe.Lap, ts, driver, mag)
	case "overtake":
		if pe.NewPlace != 0 || pe.OldPlace != 0 {
			return fmt.Sprintf("Vuelta %d [%s]: %s adelanta a %s (P%d -> P%d)", pe.Lap, ts, driver, other, pe.OldPlace, pe.NewPlace)
		}
		return fmt.Sprintf("Vuelta %d [%s]: %s adelanta a %s", pe.Lap, ts, driver, other)
	case "proximity":
		gap := pe.GapSeconds
		if gap == 0 {
			gap = pe.Gap
		}
		return fmt.Sprintf("Vuelta %d [%s]: %s a %.3fs de %s", pe.Lap, ts, driver, gap, other)
	case "off_track":
		if pe.NumWheelsOff > 0 {
			return fmt.Sprintf("Vuelta %d [%s]: %s se sale de pista (%d ruedas fuera)", pe.Lap, ts, driver, pe.NumWheelsOff)
		}
		return fmt.Sprintf("Vuelta %d [%s]: %s se sale de pista", pe.Lap, ts, driver)
	case "pit_entry":
		reason := firstNonEmpty(pe.PitReason, pe.Reason)
		if reason != "" {
			return fmt.Sprintf("Vuelta %d [%s]: %s entra en boxes (%s)", pe.Lap, ts, driver, reason)
		}
		return fmt.Sprintf("Vuelta %d [%s]: %s entra en boxes", pe.Lap, ts, driver)
	case "penalty":
		return fmt.Sprintf("Vuelta %d [%s]: Sancion para %s (total: %d)", pe.Lap, ts, driver, pe.PenaltyCount)
	case "fastest_lap":
		lapTime := pe.LapTime
		if lapTime == 0 {
			lapTime = pe.BestLapTime
		}
		return fmt.Sprintf("Vuelta %d [%s]: Vuelta rapida de %s en %.3fs", pe.Lap, ts, driver, lapTime)
	default:
		return fmt.Sprintf("Vuelta %d [%s]: %s - %s", pe.Lap, ts, pe.Type, driver)
	}
}

func resolveDrivers(pe pluginEvent) (string, string) {
	driver := strings.TrimSpace(pe.Driver)
	other := strings.TrimSpace(pe.Other)

	if len(pe.DriversInvolved) > 0 {
		if driver == "" {
			driver = strings.TrimSpace(pe.DriversInvolved[0])
		}
		if len(pe.DriversInvolved) > 1 && other == "" {
			other = strings.TrimSpace(pe.DriversInvolved[1])
		}
	}

	if driver == "" {
		driver = "Piloto"
	}
	if other == "" {
		other = "otro piloto"
	}
	return driver, other
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if strings.TrimSpace(v) != "" {
			return strings.TrimSpace(v)
		}
	}
	return ""
}

func formatTimestamp(seconds float64) string {
	total := int(math.Round(seconds))
	h := total / 3600
	m := (total % 3600) / 60
	s := total % 60
	return fmt.Sprintf("%02d:%02d:%02d", h, m, s)
}
