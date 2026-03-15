package tpcp

import (
	"crypto/rand"
	"fmt"
)

// randomUUID generates a random UUID v4. Panics if the OS random source fails,
// which indicates a catastrophic system failure making further operation unsafe.
func randomUUID() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic("tpcp: crypto/rand unavailable: " + err.Error())
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x",
		b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}
