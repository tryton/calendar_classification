#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import vobject
from trytond.model import ModelSQL
from trytond.tools import reduce_ids
from trytond.transaction import Transaction


class Event(ModelSQL):
    _name = 'calendar.event'

    def __init__(self):
        super(Event, self).__init__()
        self._error_messages.update({
            'transparent': 'Free',
            'opaque': 'Busy',
            })

    def search(self, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        if Transaction().user:
            domain = domain[:]
            domain = [domain,
                    ['OR',
                        [
                            ('classification', '=', 'confidential'),
                            ['OR',
                                ('calendar.owner', '=', Transaction().user),
                                ('calendar.write_users', '=', Transaction().user),
                            ],
                        ],
                        ('classification', '!=', 'confidential'),
                    ]]
        return super(Event, self).search(domain, offset=offset, limit=limit,
                order=order, count=count, query_string=query_string)

    def create(self, values):
        new_id = super(Event, self).create(values)
        if self.search([('id', '=', new_id)], count=True) != 1:
            self.raise_user_error('access_error', self._description)
        return new_id

    def _clean_private(self, record, transp):
        '''
        Clean private record

        :param record: a dictionary with record values
        :param transp: the time transparency
        '''
        summary = self.raise_user_error(transp, raise_exception=False)
        if 'summary' in record:
            record['summary'] = summary

        vevent = None
        if 'vevent' in record:
            vevent = record['vevent']
            if vevent:
                vevent = vobject.readOne(vevent)
                if hasattr(vevent, 'summary'):
                    vevent.summary.value = summary

        for field, value in (
                ('description', ''),
                ('categories', []),
                ('location', False),
                ('status', ''),
                ('organizer', ''),
                ('attendees', []),
                ('alarms', [])):
            if field in record:
                record[field] = value
            if field + '.rec_name' in record:
                record[field + '.rec_name'] = ''
            if vevent:
                if hasattr(vevent, field):
                    delattr(vevent, field)
        if vevent:
            record['vevent'] = vevent.serialize()

    def read(self, ids, fields_names=None):
        rule_obj = self.pool.get('ir.rule')
        cursor = Transaction().cursor
        int_id = False
        if isinstance(ids, (int, long)):
            int_id = True
            ids = [ids]
        if len({}.fromkeys(ids)) != self.search([('id', 'in', ids)],
                count=True):
            self.raise_user_error('access_error', self._description)

        writable_ids = []
        domain1, domain2 = rule_obj.domain_get(self._name, mode='write')
        if domain1:
            for i in range(0, len(ids), cursor.IN_MAX):
                sub_ids = ids[i:i + cursor.IN_MAX]
                red_sql, red_ids = reduce_ids('id', sub_ids)
                cursor.execute('SELECT id FROM "' + self._table + '" ' \
                        'WHERE ' + red_sql + ' AND (' + domain1 + ')',
                        red_ids + domain2)
                writable_ids.extend(x[0] for x in cursor.fetchall())
        else:
            writable_ids = ids
        writable_ids = set(writable_ids)

        if fields_names is None:
            fields_names = []
        fields_names = fields_names[:]
        to_remove = set()
        for field in ('classification', 'calendar', 'transp'):
            if field not in fields_names:
                fields_names.append(field)
                to_remove.add(field)
        res = super(Event, self).read(ids, fields_names=fields_names)
        for record in res:
            if record['classification'] == 'private' \
                    and record['id'] not in writable_ids:
                self._clean_private(record, record['transp'])
            for field in to_remove:
                del record[field]
        if int_id:
            return res[0]
        return res

    def write(self, ids, values):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if len({}.fromkeys(ids)) != self.search([('id', 'in', ids)],
                count=True):
            self.raise_user_error('access_error', self._description)
        res = super(Event, self).write(ids, values)
        if len({}.fromkeys(ids)) != self.search([('id', 'in', ids)],
                count=True):
            self.raise_user_error('access_error', self._description)
        return res

    def delete(self, ids):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if len({}.fromkeys(ids)) != self.search([('id', 'in', ids)],
                count=True):
            self.raise_user_error('access_error', self._description)
        return super(Event, self).delete(ids)

Event()
