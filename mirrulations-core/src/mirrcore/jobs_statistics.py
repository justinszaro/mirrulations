DOCKETS_DONE = "num_dockets_done"
DOCUMENTS_DONE = "num_documents_done"
COMMENTS_DONE = "num_comments_done"
ATTACHMENTS_DONE = 'num_attachments_done'

REGULATIONS_TOTAL_DOCKETS = 'regulations_total_dockets'
REGULATIONS_TOTAL_DOCUMENTS = 'regulations_total_documents'
REGULATIONS_TOTAL_COMMENTS = 'regulations_total_comments'


class JobStatistics:

    def __init__(self, cache):
        self.cache = cache

        self._check_keys_exist()

    def _check_keys_exist(self):
        """
        Keys that should not be overwritten
        """
        if not self.cache.exists(DOCKETS_DONE):
            self.cache.set(DOCKETS_DONE, 0)
        if not self.cache.exists(DOCUMENTS_DONE):
            self.cache.set(DOCUMENTS_DONE, 0)
        if not self.cache.exists(COMMENTS_DONE):
            self.cache.set(COMMENTS_DONE, 0)
        if not self.cache.exists(ATTACHMENTS_DONE):
            self.cache.set(ATTACHMENTS_DONE, 0)

    def get_jobs_done(self):
        dockets = int(self.cache.get(DOCKETS_DONE))
        documents = int(self.cache.get(DOCUMENTS_DONE))
        comments = int(self.cache.get(COMMENTS_DONE))
        attachments = int(self.cache.get(ATTACHMENTS_DONE))

        return {
            'num_jobs_done': dockets + documents + comments + attachments,
            DOCKETS_DONE: dockets,
            DOCUMENTS_DONE: documents,
            COMMENTS_DONE: comments,
            ATTACHMENTS_DONE: attachments
        }

    def increase_jobs_done(self, job_type):
        if job_type == "dockets":
            self.cache.incr(DOCKETS_DONE)
        elif job_type == 'documents':
            self.cache.incr(DOCUMENTS_DONE)
        elif job_type == 'comments':
            self.cache.incr(COMMENTS_DONE)
        elif job_type == 'attachment':
            self.cache.incr(ATTACHMENTS_DONE)

    def set_regulations_data(self, data_counts):
        """
        Sets the total number of dockets, documents, and comments
        in Regulations.gov with Redis values

        PARAMETERS
        ------------
        data_counts: an array like:
          [dockets_total, documents_total, comments_total]

        """
        self.cache.set(REGULATIONS_TOTAL_DOCKETS, data_counts[0])
        self.cache.set(REGULATIONS_TOTAL_DOCUMENTS, data_counts[1])
        self.cache.set(REGULATIONS_TOTAL_COMMENTS, data_counts[2])

    def get_data_totals(self):
        """
        Gets the total number of dockets, documents, and comments
        in Regulations.gov from the values in Redis.
        """
        dockets_total = int(self.cache.get(REGULATIONS_TOTAL_DOCKETS))
        documents_total = int(self.cache.get(REGULATIONS_TOTAL_DOCUMENTS))
        comments_total = int(self.cache.get(REGULATIONS_TOTAL_COMMENTS))
        return {
            REGULATIONS_TOTAL_DOCKETS: dockets_total,
            REGULATIONS_TOTAL_DOCUMENTS: documents_total,
            REGULATIONS_TOTAL_COMMENTS: comments_total
        }
