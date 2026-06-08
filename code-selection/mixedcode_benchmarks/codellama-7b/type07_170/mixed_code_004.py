def agc_mixed_004_01(self, use_dict=None, as_class=dict):
        """Return the contents of an object as a dict."""
        if use_dict is None:
            use_dict = {}
        if self.is_empty():
            return use_dict
        if self.is_list():
            for item in self:
                item.bvlpdu_contents(use_dict, as_class)
        else:
            if self.is_container():
                use_dict[self.name] = as_class()
            for key, value in self.items():
                value.bvlpdu_contents(use_dict[self.name], as_class)
        return use_dict 

def hwc_mixed_004_02(self, session_cookies):
        """Loads session cookies

        :param session_cookies: A dictionay containing session cookies
        :type session_cookies: dict
        :return: False if `session_cookies` does not contain proper cookies
        :rtype: bool
        """
        # Quick check to see if session_cookies is formatted properly
        if not session_cookies or "c_user" not in session_cookies:
            return False

        try:
            # Load cookies into current session
            self._session.cookies = requests.cookies.merge_cookies(
                self._session.cookies, session_cookies
            )
            self._postLogin()
        except Exception as e:
            log.exception("Failed loading session")
            self._resetValues()
            return False
        return True 

def hwc_mixed_004_03(self, val_list):
        """Formats value list from Munin Graph and returns multi-line value
        entries for the plugin fetch cycle.

        @param val_list: List of name-value pairs. 
        @return:         Multi-line text.

        """
        vals = []
        for (name, val) in val_list:
            if val is not None:
                if isinstance(val, float):
                    vals.append("%s.value %f" % (name, val))
                else:
                    vals.append("%s.value %s" % (name, val))
            else:
                vals.append("%s.value U" % (name,))
        return "\n".join(vals) 

def hwc_mixed_004_04(json_data):
    """
    return a list of GradDegree objects.
    """
    requests = []
    for item in json_data:
        degree = GradDegree()
        degree.degree_title = item["degreeTitle"]
        degree.exam_place = item["examPlace"]
        degree.exam_date = parse_datetime(item.get("examDate"))
        degree.req_type = item["requestType"]
        degree.major_full_name = item["majorFullName"]
        degree.submit_date = parse_datetime(item.get("requestSubmitDate"))
        degree.decision_date = parse_datetime(item.get('decisionDate'))
        degree.status = item["status"]
        degree.target_award_year = item["targetAwardYear"]
        if item.get("targetAwardQuarter")and\
           len(item.get("targetAwardQuarter")):
            degree.target_award_quarter = item["targetAwardQuarter"].lower()

        requests.append(degree)
    return requests 

def agc_mixed_004_05(self, job_id, timeout=None):
        """
        Wait for the job given by job_id to change to COMPLETED or CANCELED. Raises a
        iceqube.exceptions.TimeoutError if timeout is exceeded before each job change.

        :param job_id: the id of the job to wait for.
        :param timeout: how long to wait for a job state change before timing out.
        """
        if timeout is None:
            timeout = self.timeout

        start_time = time.time()
        while True:
            job = self.get_job(job_id)
            if job.state == 'COMPLETED' or job.state == 'CANCELED':
                return job
            elif time.time() - start_time > timeout:
                raise TimeoutError('Timeout exceeded while waiting for job to complete')
            else:
                time.sleep(1) 

def agc_mixed_004_06(access_token, ams_account, key_delivery_url):
    """Create Media Service Asset Delivery Policy.

    Args:
        access_token (str): A valid Azure authentication token.
        ams_account (str): Media Service Account.

    Returns:
        HTTP response. JSON body.
    """
    headers = {
        "Authorization": "Bearer " + access_token,
        "Content-Type": "application/json"
    }

    body = {
        "policyId": "AssetDeliveryPolicy",
        "assetDeliveryProtocol": "SmoothStreaming",
        "assetDeliveryPolicyType": "AssetDeliveryPolicy",
        "assetDeliveryConfiguration": {
            "keyDeliveryConfiguration": {
                "keyDeliveryType": "PlayReadyLicense",
                "playReadyLicenseAcquisitionUrl": key_delivery_url
            }
        }
    }

    url = "https://" + ams_account + ".restv2.westcentralus.media.azure.net/api/Assets('nb:cid:UUID:2d0d78a2-685a-4b14-9cf0-9afb0bb5dbfc')/DeliveryPolicies"

    response = requests.post(url, headers=headers, json=body)
    return response.json()
