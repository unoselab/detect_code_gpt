def hwc_mixed_001_01(self):
        """
        Returns combined size in bytes for all repository files
        """

        size = 0
        try:
            tip = self.get_changeset()
            for topnode, dirs, files in tip.walk('/'):
                for f in files:
                    size += tip.get_file_size(f.path)
                for dir in dirs:
                    for f in files:
                        size += tip.get_file_size(f.path)

        except RepositoryError:
            pass
        return size 

def hwc_mixed_001_02(cls, files=None):
        """
        Glob a pattern or a list of pattern static storage relative(s).
        """
        files = files or []
        if isinstance(files, str):
            files = os.path.normpath(files)
            matches = lambda path: matches_patterns(path, [files])
            return [path for path in cls.get_static_files() if matches(path)]
        elif isinstance(files, (list, tuple)):
            all_files = cls.get_static_files()
            files = [os.path.normpath(f) for f in files]
            sorted_result = []
            for pattern in files:
                sorted_result.extend([f for f in all_files if matches_patterns(f, [pattern])])
            return sorted_result 

def agc_mixed_001_03(self, *args, **kwargs):
        """
        Returns
        -------
        S : np.array
            Returns the pareto set for a problem. Points in the X space to be known to be optimal!
        """
        S = []
        for i in range(len(self.X)):
            is_pareto = True
            for j in range(len(self.X)):
                if all(self.X[j][k] >= self.X[i][k] for k in range(len(self.X[0]))):
                    if all(self.X[j][k] > self.X[i][k] for k in range(len(self.X[0]))):
                        is_pareto = False
                        break
            if is_pareto:
                S.append(self.X[i])
        return np.array(S) 

def agc_mixed_001_04(a, b, scale=1):
    """Intersection between two segments."""
    x1, y1 = a[0], a[1]
    x2, y2 = a[2], a[3]
    x3, y3 = b[0], b[1]
    x4, y4 = b[2], b[3]
    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if denominator == 0:
        return None
    u_a = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denominator
    u_b = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denominator
    if 0 <= u_a <= 1 and 0 <= u_b <= 1:
        x = x1 + u_a * (x2 - x1)
        y = y1 + u_a * (y2 - y1)
        return (x * scale, y * scale)
    else:
        return None 

def hwc_mixed_001_05(self, keyspace, token):
        """
        Get  a set of :class:`.Host` instances representing all of the
        replica nodes for a given :class:`.Token`.
        """
        tokens_to_hosts = self.tokens_to_hosts_by_ks.get(keyspace, None)
        if tokens_to_hosts is None:
            self.rebuild_keyspace(keyspace, build_if_absent=True)
            tokens_to_hosts = self.tokens_to_hosts_by_ks.get(keyspace, None)

        if tokens_to_hosts:
            # The values in self.ring correspond to the end of the
            # token range up to and including the value listed.
            point = bisect_left(self.ring, token)
            if point == len(self.ring):
                return tokens_to_hosts[self.ring[0]]
            else:
                return tokens_to_hosts[self.ring[point]]
        return [] 

def agc_mixed_001_06(self) -> List['DAGCircuit']:
        """Split DAGCircuit into independent components"""
        components = []
        visited = set()

        def dfs(node):
            if node not in visited:
                visited.add(node)
                for neighbor in node.neighbors:
                    dfs(neighbor)

        for node in self.nodes:
            if node not in visited:
                component = DAGCircuit()
                dfs(node)
                components.append(component)

        return components
