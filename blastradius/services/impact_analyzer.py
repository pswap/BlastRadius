class ImpactAnalyzer:
    """Small adapter-friendly facade for codebase impact queries."""
    def analyze(self, greptile, changed_files):
        question = "What services, events, and consumers are affected by: " + ", ".join(f.path for f in changed_files)
        return greptile.query_codebase(question)
