import time


class AcquisitionService:

    def __init__(self, retriever):
        self.retriever = retriever

    def collect(self, sources, extractors):
        collected = []

        for index, source in enumerate(sources):
            raw_content = self.retriever.fetch(source)

            if raw_content.content:
                for label, extractor in extractors.items():
                    items = extractor(
                        html=raw_content.content,
                        source=source,
                    )

                    print(f"{label}: {len(items)}")

                    collected.extend(items)

            if index < len(sources) - 1:
                time.sleep(1)

        return collected
