package web

import "embed"

//go:embed build
var EmbeddedFiles embed.FS

//go:embed build
var Static embed.FS

//go:embed test.k6.io
var TestK6IO embed.FS
