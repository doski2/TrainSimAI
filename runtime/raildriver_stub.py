class RDStub:
    def setTrainBrake(self, v: float) -> None:
        print(f"[RDStub] setTrainBrake({v})")
    def set_brake(self, v: float) -> None:
        print(f"[RDStub] set_brake({v})")
    def set_throttle(self, v: float) -> None:
        print(f"[RDStub] set_throttle({v})")

rd = RDStub()
