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
	Type      string  `json:"type"`
	Timestamp float64 `json:"timestamp"`
	Lap       int     `json:"lap"`
	Driver    string  `json:"driver"`
	Other     string  `json:"other,omitempty"`
	Summary   string  `json:"summary"`
	Position  struct {
		X float64 `json:"x"`
		Y float64 `json:"y"`
		Z float64 `json:"z"`
	} `json:"position"`
	Drivers []struct {
		Name    string  `json:"name"`
		Place   int     `json:"place"`
		X       float64 `json:"x"`
		Y       float64 `json:"y"`
		Z       float64 `json:"z"`
		LapDist float64 `json:"lap_dist"`
		Lap     int     `json:"lap"`
	} `json:"drivers,omitempty"`
	// Type-specific extra fields
	Magnitude    float64 `json:"magnitude,omitempty"`
	NewPlace     int     `json:"new_place,omitempty"`
	OldPlace     int     `json:"old_place,omitempty"`
	BestLapTime  float64 `json:"best_lap_time,omitempty"`
	Gap          float64 `json:"gap,omitempty"`
	NumWheelsOff int     `json:"num_wheels_off,omitempty"`
	Reason       string  `json:"reason,omitempty"`
	TireFront    string  `json:"tire_front,omitempty"`
	TireRear     string  `json:"tire_rear,omitempty"`
	PenaltyCount int     `json:"penalty_count,omitempty"`
}

// pluginTypeToEventType maps the "type" string from the JSON to our integer codes.
var pluginTypeToEventType = map[string]int{
	"overtake":           1,
	"collision_vehicle":  2,
	"collision_wall":     3,
	"penalty":            4,
	"pit_entry":          5,
	"off_track":          6,
	"proximity":          7,
	"fastest_lap":        8,
}

// ParsePluginJSON parses the JSON produced by the TrueVoice rF2 plugin and
// returns a RaceHeader + slice of RaceEvents compatible with the rest of the
// race pipeline.
func ParsePluginJSON(data []byte) (RaceHeader, []RaceEvent, error) {
	var pj pluginJSON
	if err := json.Unmarshal(data, &pj); err != nil {
		return RaceHeader{}, nil, fmt.Errorf("invalid plugin JSON: %w", err)
	}

	// Build header — sort grid by place
	type gridEntry struct {
		Name  string
		Place int
	}
	sorted := make([]gridEntry, len(pj.GridOrder))
	for i, g := range pj.GridOrder {
		sorted[i] = gridEntry{Name: g.Name, Place: g.Place}
	}
	sort.SliceStable(sorted, func(i, j int) bool {
		return sorted[i].Place < sorted[j].Place
	})
	grid := make([]string, len(sorted))
	for i, g := range sorted {
		grid[i] = g.Name
	}

	maxLap := 0
	for _, ev := range pj.Events {
		if ev.Lap > maxLap {
			maxLap = ev.Lap
		}
	}

	header := RaceHeader{
		TrackEvent:  pj.Header.TrackName,
		TrackLength: pj.Header.TrackLength,
		RaceLaps:    maxLap,
		NumDrivers:  pj.Header.NumVehicles,
		GridOrder:   grid,
	}

	// Convert events
	events := make([]RaceEvent, 0, len(pj.Events))
	for _, pe := range pj.Events {
		evType, ok := pluginTypeToEventType[pe.Type]
		if !ok {
			continue // skip unknown types
		}

		re := RaceEvent{
			Lap:       pe.Lap,
			Timestamp: pe.Timestamp,
			EventType: evType,
			Summary:   pluginSummary(pe),
			Position: &EventPosition{
				X: pe.Position.X,
				Y: pe.Position.Y,
				Z: pe.Position.Z,
			},
		}

		// Driver positions snapshot
		if len(pe.Drivers) > 0 {
			snaps := make([]DriverSnapshot, len(pe.Drivers))
			for i, d := range pe.Drivers {
				snaps[i] = DriverSnapshot{
					Name:    d.Name,
					Place:   d.Place,
					Pos:     EventPosition{X: d.X, Y: d.Y, Z: d.Z},
					LapDist: d.LapDist,
					Lap:     d.Lap,
				}
			}
			re.DriverPositions = snaps
		}

		// Extra data per type
		extra := map[string]any{}
		switch pe.Type {
		case "collision_vehicle":
			extra["magnitude"] = pe.Magnitude
			if pe.Other != "" {
				extra["other"] = pe.Other
			}
		case "collision_wall":
			extra["magnitude"] = pe.Magnitude
		case "overtake":
			extra["new_place"] = pe.NewPlace
			extra["old_place"] = pe.OldPlace
			if pe.Other != "" {
				extra["overtaken"] = pe.Other
			}
		case "proximity":
			extra["gap"] = pe.Gap
			if pe.Other != "" {
				extra["ahead"] = pe.Other
			}
		case "off_track":
			extra["num_wheels_off"] = pe.NumWheelsOff
		case "pit_entry":
			extra["reason"] = pe.Reason
			if pe.TireFront != "" {
				extra["tire_front"] = pe.TireFront
			}
			if pe.TireRear != "" {
				extra["tire_rear"] = pe.TireRear
			}
		case "penalty":
			extra["penalty_count"] = pe.PenaltyCount
		case "fastest_lap":
			extra["best_lap_time"] = pe.BestLapTime
		}
		if len(extra) > 0 {
			re.ExtraData = extra
		}

		events = append(events, re)
	}

	// Sort by timestamp
	sort.SliceStable(events, func(i, j int) bool {
		return events[i].Timestamp < events[j].Timestamp
	})

	return header, events, nil
}

// pluginSummary generates a human-readable Spanish summary for a plugin event.
func pluginSummary(pe pluginEvent) string {
	ts := formatTimestamp(pe.Timestamp)
	switch pe.Type {
	case "collision_vehicle":
		return fmt.Sprintf("Vuelta %d [%s]: Colision entre %s y %s (fuerza %.0f)", pe.Lap, ts, pe.Driver, pe.Other, pe.Magnitude)
	case "collision_wall":
		return fmt.Sprintf("Vuelta %d [%s]: %s choca contra el muro (fuerza %.0f)", pe.Lap, ts, pe.Driver, pe.Magnitude)
	case "overtake":
		return fmt.Sprintf("Vuelta %d [%s]: %s adelanta a %s (P%d -> P%d)", pe.Lap, ts, pe.Driver, pe.Other, pe.OldPlace, pe.NewPlace)
	case "proximity":
		return fmt.Sprintf("Vuelta %d [%s]: %s a %.3fs de %s", pe.Lap, ts, pe.Driver, pe.Gap, pe.Other)
	case "off_track":
		return fmt.Sprintf("Vuelta %d [%s]: %s se sale de pista (%d ruedas fuera)", pe.Lap, ts, pe.Driver, pe.NumWheelsOff)
	case "pit_entry":
		parts := []string{fmt.Sprintf("Vuelta %d [%s]: %s entra en boxes", pe.Lap, ts, pe.Driver)}
		if pe.Reason != "" {
			parts = append(parts, fmt.Sprintf("(%s)", pe.Reason))
		}
		tire := strings.TrimSpace(pe.TireFront)
		if tire != "" {
			parts = append(parts, fmt.Sprintf("[neumaticos: %s]", tire))
		}
		return strings.Join(parts, " ")
	case "penalty":
		return fmt.Sprintf("Vuelta %d [%s]: Sancion para %s (total: %d)", pe.Lap, ts, pe.Driver, pe.PenaltyCount)
	case "fastest_lap":
		return fmt.Sprintf("Vuelta %d [%s]: Vuelta rapida de %s en %.3fs", pe.Lap, ts, pe.Driver, pe.BestLapTime)
	default:
		return fmt.Sprintf("Vuelta %d [%s]: %s - %s", pe.Lap, ts, pe.Type, pe.Driver)
	}
}

// formatTimestamp converts elapsed seconds to HH:MM:SS.
func formatTimestamp(seconds float64) string {
	total := int(math.Round(seconds))
	h := total / 3600
	m := (total % 3600) / 60
	s := total % 60
	return fmt.Sprintf("%02d:%02d:%02d", h, m, s)
}
