from signals import ALL_SIGNALS


class SignalEngine:

    @staticmethod
    def evaluate(item):
        evidence = []

        for signal in ALL_SIGNALS:

            result = signal.evaluate(item)

            if result.detected:
                evidence.append({
                    "type": result.signal,
                    "signal": result.signal,
                    "weight": result.weight,
                    "reason": result.reason,
                })

        return evidence