package feed

import (
	"github.com/GoogleCloudPlatform/functions-framework-go/functions"
)

func init() {
	functions.HTTP("GetPlurkSearch", GetPlurkSearch)
	functions.HTTP("GetPlurkTop", GetPlurkTop)
	functions.HTTP("GetPttSearch", GetPttSearch)
}
