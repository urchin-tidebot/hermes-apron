package server

type Settings struct {
	Listen, PublicURL, StateDir, FrontendDir, MachineFile string
	TestLoopback                                          bool
	Rooms                                                 []string
}

func (s Settings) Validate() error { return nil }
