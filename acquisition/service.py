import time


class AcquisitionService:

    def __init__(self, retriever):
        self.retriever = retriever

    def collect(self, sources, extractors):
        collected = []

        for index, source in enumerate(sources):
            try:
                raw_content = self.retriever.fetch(source)

            except Exception as error:
                self._log_stage_failure(
                    stage="retrieval",
                    source=source,
                    error=error,
                )

                raw_content = None

            if raw_content and raw_content.content:
                for label, extractor in extractors.items():
                    try:
                        items = extractor(
                            html=raw_content.content,
                            source=source,
                        )

                    except Exception as error:
                        self._log_stage_failure(
                            stage=label,
                            source=source,
                            error=error,
                        )

                        continue

                    print(f"{label}: {len(items)}")

                    collected.extend(items)

            if index < len(sources) - 1:
                time.sleep(1)

        return collected

    @staticmethod
    def _log_stage_failure(stage, source, error):
        identifier = (
            source.get("name")
            or source.get("url")
            or "unknown source"
        )

        print(
            f"[AcquisitionService] {stage} failed for "
            f"{identifier}: {type(error).__name__}: {error}"
        )
