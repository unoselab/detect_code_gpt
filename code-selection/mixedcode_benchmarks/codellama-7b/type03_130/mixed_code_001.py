def hwc_mixed_001_01(self, record):
        """
        Updates the trees with the given training record.
        """
        self._fell_trees()
        self._grow_trees()
        for tree in self.trees:
            if random.random() < self.sample_ratio:
                tree.train(record)
            else:
                tree.out_of_bag_samples.append(record)
                while len(tree.out_of_bag_samples) > self.max_out_of_bag_samples:
                    tree.out_of_bag_samples.pop(0) 

def hwc_mixed_001_02(self, pool):
        """AddAgentPool.
        [Preview API] Create an agent pool.
        :param :class:`<TaskAgentPool> <azure.devops.v5_1.task_agent.models.TaskAgentPool>` pool: Details about the new agent pool
        :rtype: :class:`<TaskAgentPool> <azure.devops.v5_1.task-agent.models.TaskAgentPool>`
        """
        content = self._serialize.body(pool, 'TaskAgentPool')
        response = self._send(http_method='POST',
                              location_id='a8c47e17-4d56-4a56-92bb-de7ea7dc65be',
                              version='5.1-preview.1',
                              content=content)
        return self._deserialize('TaskAgentPool', response) 

def agc_mixed_001_03(elem, seq_expr):
        """
        Return True if elem (an element of elem_list) matches seq_expr, an element in self.sequence
        """
        if isinstance(seq_expr, str):
            return elem == seq_expr
        elif isinstance(seq_expr, list):
            return elem in seq_expr
        elif isinstance(seq_expr, tuple):
            return elem in seq_expr
        elif isinstance(seq_expr, dict):
            return elem in seq_expr.keys()
        else:
            raise ValueError("Invalid sequence expression: %s" % seq_expr) 

def agc_mixed_001_04(self, res):
        """Inform about the result of the test. If res is not a string, displays
        'yes' or 'no' depending on whether res is evaluated as true or false.
        The result is only displayed when self.did_show_result is not set.
        """
        if self.did_show_result:
            return
        if isinstance(res, str):
            self.did_show_result = True
            self.write(res)
        elif res:
            self.did_show_result = True
            self.write('yes')
        else:
            self.did_show_result = True
            self.write('no') 

def hwc_mixed_001_05(self, key, parser_result):
        """ Given a type and a dict of parser results, return
        the items as a list.
        """
        try:
            list_data = parser_result[key].asList()
            if any(isinstance(obj, str) for obj in list_data):
                txt_lines = [''.join(list_data)]
            else:
                txt_lines = [''.join(f) for f in list_data]
        except KeyError:
            txt_lines = []
        return txt_lines 

def agc_mixed_001_06(
            self,
            assoc_id,
            evidence_line_bnode
    ):
        """
        Add assertion level provenance, currently always IMPC
        :param assoc_id:
        :param evidence_line_bnode:
        :return:
        """
        self.graph.add(
            (
                assoc_id,
                self.graph.namespace_manager.compute_qname(
                    "prov:wasDerivedFrom"
                ),
                evidence_line_bnode
            )
        )
