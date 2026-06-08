def agc_mixed_004_01(id):
    """ Returns a group from the DCOS Enterprise.  It returns None if none exists.

        :param id: group id
        :type id: str
        :return: Group
        :rtype: dict
    """
    groups = {
        "group1": {
            "id": "group1",
            "description": "Group 1",
            "users": ["user1", "user2"],
            "groups": ["group2"],
        },
        "group2": {
            "id": "group2",
            "description": "Group 2",
            "users": ["user3"],
            "groups": [],
        },
    }
    if id in groups:
        return groups[id]
    else:
        return None 

async def agc_mixed_004_02(self, status, avatar=None):
        """Generate a discord status icon below the image provided.

        This function is a coroutine.

        Parameters:
            status: str - a discord status, must be online, idle, dnd, or streaming
            avatar: str - http/s url pointing to an avatar, has to have proper headers and be a direct link to an image
                    (Note, this url is encoded by the wrapper itself, so you don't have to worry about encoding it ;))

        Return Type: image data"""
        if status not in ("online", "idle", "dnd", "streaming"):
            raise ValueError("Invalid status provided.")
        if avatar is not None:
            if not avatar.startswith(("http://", "https://")):
                raise ValueError("Invalid avatar URL provided.")
            if not self.is_image_url(avatar):
                raise ValueError("Invalid avatar URL provided.")
        status_image = Image.open(f"path/to/status_{status}.png")
        if avatar is not None:
            avatar_image = Image.open(urllib.request.urlopen(avatar))
            avatar_image = avatar_image.resize((32, 32))
            status_image.paste(avatar_image, (16, 16))
        return status_image 

def hwc_mixed_004_03():
    """returns a list of files that should be watched by the Flask server
    when in debug mode to trigger a reload of the server
    """
    FILES_TO_SKIP = ["src/gdbgui.js"]
    THIS_DIR = os.path.dirname(os.path.abspath(__file__))
    extra_dirs = [THIS_DIR]
    extra_files = []
    for extra_dir in extra_dirs:
        for dirname, _, files in os.walk(extra_dir):
            for filename in files:
                filepath = os.path.join(dirname, filename)
                if os.path.isfile(filepath) and filepath not in extra_files:
                    for skipfile in FILES_TO_SKIP:
                        if skipfile not in filepath:
                            extra_files.append(filepath)
    return extra_files 

def hwc_mixed_004_04(self, keyspace, token):
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

def hwc_mixed_004_05(df, other):
    """
    Helper function to ensure that DataFrames are valid for set operations.
    Columns must be the same name in the same order, and indices must be of the
    same dimension with the same names.
    """

    if df.columns.values.tolist() != other.columns.values.tolist():
        not_in_df = [col for col in other.columns if col not in df.columns]
        not_in_other = [col for col in df.columns if col not in other.columns]
        error_string = 'Error: not compatible.'
        if len(not_in_df):
            error_string += ' Cols in y but not x: ' + str(not_in_df) + '.'
        if len(not_in_other):
            error_string += ' Cols in x but not y: ' + str(not_in_other) + '.'
        raise ValueError(error_string)
    if len(df.index.names) != len(other.index.names):
        raise ValueError('Index dimension mismatch')
    if df.index.names != other.index.names:
        raise ValueError('Index mismatch')
    else:
        return 

def agc_mixed_004_06(mx_lvl, E, sz_cl, seed=None):
    """
    This function generates a directed network with a hierarchical modular
    organization. All modules are fully connected and connection density
    decays as 1/(E^n), with n = index of hierarchical level.

    Parameters
    ----------
    mx_lvl : int
        number of hierarchical levels, N = 2^mx_lvl
    E : int
        connection density fall off per level
    sz_cl : int
        size of clusters (must be power of 2)
    seed : hashable, optional
        If None (default), use the np.random's global random state to generate random numbers.
        Otherwise, use a new np.random.RandomState instance seeded with the given value.

    Returns
    -------
    CIJ : NxN np.ndarray
        connection matrix
    K : int
        number of connections present in output CIJ
    """
    if seed is not None:
        np.random.seed(seed)
    N = 2**mx_lvl
    CIJ = np.zeros((N, N))
    for lvl in range(mx_lvl):
        n_cl = 2**lvl
        cl_sz = N // n_cl
        for i in range(n_cl):
            for j in range(n_cl):
                if i!= j:
                    p = 1 / (E**lvl)
                    if np.random.rand() < p:
                        CIJ[i*cl_sz:(i+1)*cl_sz, j*cl_sz:(j+1)*cl_sz] = 1
    K = np.sum(CIJ)
    return CIJ, int(K)
