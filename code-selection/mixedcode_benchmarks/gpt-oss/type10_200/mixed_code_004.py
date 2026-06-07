def agc_mixed_004_01(self, funcTilde, R, z, phi):
        """
        NAME:
           _computeArray
        PURPOSE:
           evaluate the density or potential for a given array of coordinates
        INPUT:
           funcTidle - must be _rhoTilde or _phiTilde
           R - Cylindrical Galactocentric radius
           z - vertical height
           phi - azimuth
        OUTPUT:
           density or potential evaluated at (R,z, phi)
        HISTORY:
           2016-06-02 - Written - Aladdin 
        """
        import numpy as np
        # Convert inputs to arrays and broadcast to a common shape
        R_arr, z_arr, phi_arr = np.broadcast_arrays(
            np.asarray(R, dtype=float),
            np.asarray(z, dtype=float),
            np.asarray(phi, dtype=float)
        )
        # Try direct evaluation (funcTilde may already support array inputs)
        try:
            result = funcTilde(R_arr, z_arr, phi_arr)
        except Exception:
            # Fall back to element‑wise evaluation
            vec = np.vectorize(funcTilde, otypes=[float])
            result = vec(R_arr, z_arr, phi_arr)
        return result 

def agc_mixed_004_02():
    """
    If ngrok is running, it exposes an API on port 4040. We can use that
    to figure out what URL it has assigned, and suggest that to the user.
    https://ngrok.com/docs#list-tunnels
    """
    import json
    from urllib.request import urlopen, Request
    from urllib.error import URLError, HTTPError

    api_url = "http://127.0.0.1:4040/api/tunnels"
    try:
        with urlopen(Request(api_url, headers={"User-Agent": "python"}), timeout=1) as resp:
            data = resp.read().decode("utf-8")
        payload = json.loads(data)
        tunnels = payload.get("tunnels", [])
        # Prefer HTTPS tunnels, otherwise return the first available
        for t in tunnels:
            if t.get("proto") == "https" and "public_url" in t:
                return t["public_url"]
        if tunnels and "public_url" in tunnels[0]:
            return tunnels[0]["public_url"]
    except (URLError, HTTPError, json.JSONDecodeError, OSError):
        pass
    return None 

def hwc_mixed_004_03(self):
        """Get all properties of a given index"""

        properties = {}
        r = self.requests.get(self.index_url + "/_mapping", headers=HEADER_JSON, verify=False)
        try:
            r.raise_for_status()
            r_json = r.json()

            if 'items' not in r_json[self.index]['mappings']:
                return properties

            if 'properties' not in r_json[self.index]['mappings']['items']:
                return properties

            properties = r_json[self.index]['mappings']['items']['properties']
        except requests.exceptions.HTTPError as ex:
            logger.error("Error all attributes for %s.", self.anonymize_url(self.index_url))
            logger.error(ex)
            return

        return properties 

def hwc_mixed_004_04(self):
        """Launches a new server instance."""
        self.server_attrs = self.consul.create_server(
                "%s-%s" % (self.stack.name, self.name),
                self.disk_image_id,
                self.instance_type,
                self.ssh_key_name,
                tags=self.tags,
                availability_zone=self.availability_zone,
                timeout_s=self.launch_timeout_s,
                security_groups=self.security_groups,
                **self.provider_extras
                )
        log.debug('Post launch delay: %d s' % self.post_launch_delay_s)
        time.sleep(self.post_launch_delay_s) 

def agc_mixed_004_05(self, data):
        """ 
        It extracts irc msg arguments. 
        """
        args = []
        while data:
            if data[0] == ':':
                args.append(data[1:])
                break
            if ' ' in data:
                token, data = data.split(' ', 1)
                args.append(token)
                data = data.lstrip()
            else:
                args.append(data)
                break
        return args 

def hwc_mixed_004_06(self, F, a, b):
        """
        Forward of Decomposable Attention layer
        """
        # a.shape = [B, L1, H]
        # b.shape = [B, L2, H]
        # extract features
        tilde_a = self.f(a)  # shape = [B, L1, H]
        tilde_b = self.f(b)  # shape = [B, L2, H]
        # attention
        # e.shape = [B, L1, L2]
        e = F.batch_dot(tilde_a, tilde_b, transpose_b=True)
        # beta: b align to a, [B, L1, H]
        beta = F.batch_dot(e.softmax(), tilde_b)
        # alpha: a align to b, [B, L2, H]
        alpha = F.batch_dot(e.transpose([0, 2, 1]).softmax(), tilde_a)
        # compare
        feature1 = self.g(F.concat(tilde_a, beta, dim=2))
        feature2 = self.g(F.concat(tilde_b, alpha, dim=2))
        feature1 = feature1.sum(axis=1)
        feature2 = feature2.sum(axis=1)
        yhat = self.h(F.concat(feature1, feature2, dim=1))
        return yhat
