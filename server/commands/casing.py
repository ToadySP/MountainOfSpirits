import re

from server import database
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError

from . import mod_only

__all__ = [
	'ooc_cmd_doc',
	'ooc_cmd_cleardoc',
	'ooc_cmd_evidence_mod',
	'ooc_cmd_evi_swap',
	'ooc_cmd_cm',
	'ooc_cmd_uncm',
	'ooc_cmd_setcase',
	'ooc_cmd_anncase',
	'ooc_cmd_blockwtce',
	'ooc_cmd_unblockwtce',
	'ooc_cmd_judgelog',
	'ooc_cmd_woosh',
	'ooc_cmd_testimony',
	'ooc_cmd_cleartestimony'
]

def ooc_cmd_testimony(client, arg):
	if len(client.area.recorded_messages) == 0:
		raise ArgumentError('No recorded testimony in this area.')
	testimony = 'Testimony:'
	testimonylength = len(client.area.recorded_messages) - 1
	index = 0
	statements = []
	for statement in client.area.recorded_messages:
		statements.append(index)
		index += 1
	for statement in client.area.recorded_messages:
		statements[statement.id] = statement
	index = 0
	for n in statements:
		statement = statements[index]
		index += 1
		if statement.id == 0:
			testimony += f'\n{statement.args[4]}'
		elif statement.id == testimonylength:
			testimony += f'\n{statement.args[4]}'
		else:
			testimony += f'\n{statement.id}: {statement.args[4]}'
	client.send_ooc(testimony)

def ooc_cmd_woosh(client, arg):
	"""
	Prevent a user from using Witness Testimony/Cross Examination buttons
	as a judge.
	Usage: /woosh
	"""
	if len(arg) != 0:
		raise ArgumentError('This command takes no arguments.')
	if client.can_wtce:
		client.can_wtce = False
		client.send_ooc('You will no longer use judge signs.')
	else:
		client.can_wtce = True
		client.send_ooc('You will now use judge signs again.')

def ooc_cmd_doc(client, arg):
	"""
	Show or change the link for the current case document.
	Usage: /doc [url]
	"""
	if len(arg) == 0:
		client.send_ooc(f'Document: {client.area.doc}')
		database.log_room('doc.request', client, client.area)
	elif client in client.area.owners or client.is_mod:
		client.area.change_doc(arg)
		client.area.broadcast_ooc('{} changed the doc link.'.format(
			client.char_name))
		database.log_room('doc.change', client, client.area, message=arg)
	else:
		client.send_ooc('You must be CM to change the doc.')

def ooc_cmd_cleartestimony(client, arg):
	if client in client.area.owners:
		client.area.recorded_messages.clear()
		client.area.statement = 0
		client.area.is_recording = False
		client.send_ooc('Testimony cleared.')

def ooc_cmd_cleardoc(client, arg):
	"""
	Clear the link for the current case document.
	Usage: /cleardoc
	"""
	if len(arg) != 0:
		raise ArgumentError('This command has no arguments.')
	if client in client.area.owners or client.is_mod:
		client.area.change_doc()
		client.area.broadcast_ooc('{} cleared the doc link.'.format(
			client.char_name))
		database.log_room('doc.clear', client, client.area)
	else:
		client.send_ooc('You must be CM to change the doc.')

@mod_only()
def ooc_cmd_evidence_mod(client, arg):
	"""
	Change the evidence privilege mode. Refer to the documentation
	for more information on the function of each mode.
	Usage: /evidence_mod <FFA|Mods|CM|HiddenCM>
	"""
	if not arg or arg == client.area.evidence_mod:
		client.send_ooc(
			f'current evidence mod: {client.area.evidence_mod}')
	elif arg in ['FFA', 'Mods', 'CM', 'HiddenCM']:
		if client.area.evidence_mod == 'HiddenCM':
			for i in range(len(client.area.evi_list.evidences)):
				client.area.evi_list.evidences[i].pos = 'all'
		client.area.evidence_mod = arg
		client.send_ooc(
			f'current evidence mod: {client.area.evidence_mod}')
		database.log_room('evidence_mod', client, client.area, message=arg)
	else:
		raise ArgumentError(
			'Wrong Argument. Use /evidence_mod <MOD>. Possible values: FFA, CM, Mods, HiddenCM'
		)


def ooc_cmd_evi_swap(client, arg):
	"""
	Swap the positions of two evidence items on the evidence list.
	Usage: /evi_swap <id> <id>
	"""
	args = list(arg.split(' '))
	if len(args) != 2:
		raise ClientError("you must specify 2 numbers")
	try:
		client.area.evi_list.evidence_swap(client, int(args[0]), int(args[1]))
		client.area.broadcast_evidence_list()
	except:
		raise ClientError("you must specify 2 numbers")


def ooc_cmd_cm(client, arg):
	"""
	Add a case manager for the current room.
	Usage: /cm <id>
	"""
	if 'CM' not in client.area.evidence_mod and not client.is_mod:
		raise ClientError('You can\'t become a CM in this area')
	if len(client.area.owners) == 0 and len(arg) == 0:
		client.area.owners.append(client)
		if client.area.evidence_mod == 'HiddenCM':
			client.area.broadcast_evidence_list()
		if client.area.sub:
			client.area.hub.sub_arup_cms()
		elif client.area.is_hub:
			for sub in client.area.subareas:
				sub.owners.append(client)
				if sub.is_restricted:
					sub.conn_arup_cms()
			client.area.sub_arup_cms()
			client.server.area_manager.send_arup_cms()
		else:
			client.server.area_manager.send_arup_cms()
		if not client.ghost:
			client.area.broadcast_ooc('{} [{}] is CM in this area now.'.format(client.char_name, client.id))
		else:
			client.send_ooc('You are now ghost CM of this area.')
		database.log_room('cm.add', client, client.area, target=client, message='self-added')
	elif not client.is_mod and len(client.area.owners) > 0 and len(arg) == 0:
		notghost = False
		for c in client.area.owners:
			if not c.ghost:
				notghost = True
		if notghost == False:
			client.area.owners.append(client)
			if client.area.evidence_mod == 'HiddenCM': 
				client.area.broadcast_evidence_list()
			if client.area.sub:
				client.area.hub.sub_arup_cms()
			elif client.area.is_hub:
				for sub in client.area.subareas:
					sub.owners.append(client)
					if sub.is_restricted:
						sub.conn_arup_cms()
				client.area.sub_arup_cms()
				client.server.area_manager.send_arup_cms()
			else:
				client.server.area_manager.send_arup_cms()
			if not client.ghost: 
				client.area.broadcast_ooc('{} [{}] is CM in this area now.'.format(client.char_name, client.id))
			database.log_room('cm.add', client, client.area, target=client, message='self-added')
	elif client.is_mod and len(arg) == 0:
		client.area.owners.append(client)
		if client.area.evidence_mod == 'HiddenCM':
			client.area.broadcast_evidence_list()
		if client.area.sub:
			client.area.hub.sub_arup_cms()
		elif client.area.is_hub:
			for sub in client.area.subareas:
				sub.owners.append(client)
				if sub.is_restricted:
					sub.conn_arup_cms()
			client.area.sub_arup_cms()
			client.server.area_manager.send_arup_cms()
		else:
			client.server.area_manager.send_arup_cms()
		if not client.ghost:
			client.area.broadcast_ooc('{} [{}] is CM in this area now.'.format(client.char_name, client.id))
		else:
			client.send_ooc('You are now ghost CM of this area.')
		database.log_room('cm.add', client, client.area, target=client, message='self-added')
	elif client in client.area.owners or client.is_mod:
		if len(arg) > 0:
			arg = arg.split(' ')
			if client not in client.area.owners and not client.is_mod:
				raise ArgumentError('You can\'t nominate someone when you aren\'t the CM.')
		for id in arg:
			try:
				id = int(id)
				c = client.server.client_manager.get_targets(client, TargetType.ID, id, False)[0]
				if not c in client.area.clients and not client.is_mod:
					raise ArgumentError('You can only \'nominate\' people to be CMs when they are in the area.')
				elif c in client.area.owners:
					client.send_ooc('{} [{}] is already a CM here.'.format(c.char_name, c.id))
				else:
					client.area.owners.append(c)
					if client.area.evidence_mod == 'HiddenCM':
						client.area.broadcast_evidence_list()
					if client.area.sub:
						client.area.hub.sub_arup_cms()
					elif client.area.is_hub:
						for sub in client.area.subareas:
							sub.owners.append(c)
							if sub.is_restricted:
								sub.conn_arup_cms()
						client.area.sub_arup_cms()
						client.server.area_manager.send_arup_cms()
					else:
						client.server.area_manager.send_arup_cms()
					client.area.broadcast_ooc('{} [{}] is CM in this area now.'.format(c.char_name, c.id))
					database.log_room('cm.add', client, client.area, target=c)
			except:
				client.send_ooc(f'{id} does not look like a valid ID.')
	else:
		raise ClientError('You must be authorized to do that.')

def ooc_cmd_uncm(client, arg):
	"""
	Remove a case manager from the current area.
	Usage: /uncm <id>
	"""
	if client not in client.area.owners and not client.is_mod:
		raise ClientError('You must be a CM.')
	elif len(arg) > 0:
		arg = arg.split(' ')
	else:
		arg = [client.id]
	for id in arg:
		try:
			id = int(id)
			c = client.server.client_manager.get_targets(
				client, TargetType.ID, id, False)[0]
			if c in client.area.owners:
				client.area.owners.remove(c)
				if client.area.sub:
					client.area.hub.sub_arup_cms()
				elif client.area.is_hub:
					for sub in client.area.subareas:
						sub.owners.remove(client)
						if sub.is_restricted:
							sub.conn_arup_cms()
					client.area.sub_arup_cms()
					client.server.area_manager.send_arup_cms()
				else:
					client.server.area_manager.send_arup_cms()
				if not client.ghost:
					client.area.broadcast_ooc('{} [{}] is no longer CM in this area.'.format(c.char_name, c.id))
				else:
					client.send_ooc('You are no longer ghost CM of this area.')
				database.log_room('cm.remove', client, client.area, target=c)
				if len(client.area.owners) == 0:
					client.area.is_recording = False
					client.area.recorded_messages = []
					client.area.statement = 0
			else:
				client.send_ooc(
					'You cannot remove someone from CMing when they aren\'t a CM.'
				)
		except:
			client.send_ooc(
				f'{id} does not look like a valid ID.')

# LEGACY
def ooc_cmd_setcase(client, arg):
	"""
	Set the positions you are interested in taking for a case.
	(This command is used internally by the 2.6 client.)
	"""
	args = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', arg)
	if len(args) == 0:
		raise ArgumentError('Please do not call this command manually!')
	else:
		client.casing_cases = args[0]
		client.casing_cm = args[1] == "1"
		client.casing_def = args[2] == "1"
		client.casing_pro = args[3] == "1"
		client.casing_jud = args[4] == "1"
		client.casing_jur = args[5] == "1"
		client.casing_steno = args[6] == "1"


# LEGACY
def ooc_cmd_anncase(client, arg):
	"""
	Announce that a case is currently taking place in this area,
	needing a certain list of positions to be filled up.
	Usage: /anncase <message> <def> <pro> <jud> <jur> <steno>
	"""
	# XXX: Merge with aoprotocol.net_cmd_casea
	if client in client.area.owners:
		if not client.can_call_case():
			raise ClientError(
				'Please wait 60 seconds between case announcements!')
		args = re.findall(r'(?:[^\s,"]|"(?:\\.|[^"])*")+', arg)
		if len(args) == 0:
			raise ArgumentError('Please do not call this command manually!')
		elif len(args) == 1:
			raise ArgumentError(
				'You should probably announce the case to at least one person.'
			)
		else:
			if not args[1] == "1" and not args[2] == "1" and not args[
					3] == "1" and not args[4] == "1" and not args[5] == "1":
				raise ArgumentError(
					'You should probably announce the case to at least one person.'
				)
			msg = '=== Case Announcement ===\r\n{} [{}] is hosting {}, looking for '.format(
				client.char_name, client.id, args[0])

			lookingfor = [p for p, q in
				zip(['defense', 'prosecutor', 'judge', 'juror', 'stenographer'], args[1:])
				if q == '1']

			msg += ', '.join(lookingfor) + '.\r\n=================='

			client.server.send_all_cmd_pred('CASEA', msg, args[1], args[2],
											args[3], args[4], args[5], '1')

			client.set_case_call_delay()

			log_data = {k: v for k, v in
				zip(('message', 'def', 'pro', 'jud', 'jur', 'steno'), args)}
			database.log_room('case', client, client.area, message=log_data)
	else:
		raise ClientError(
			'You cannot announce a case in an area where you are not a CM!')


@mod_only()
def ooc_cmd_blockwtce(client, arg):
	"""
	Prevent a user from using Witness Testimony/Cross Examination buttons
	as a judge.
	Usage: /blockwtce <id>
	"""
	if len(arg) == 0:
		raise ArgumentError('You must specify a target. Use /blockwtce <id>.')
	try:
		targets = client.server.client_manager.get_targets(
			client, TargetType.ID, int(arg), False)
	except:
		raise ArgumentError('You must enter a number. Use /blockwtce <id>.')
	if not targets:
		raise ArgumentError('Target not found. Use /blockwtce <id>.')
	for target in targets:
		target.can_wtce = False
		target.send_ooc(
			'A moderator blocked you from using judge signs.')
		database.log_room('blockwtce', client, client.area, target=target)
	client.send_ooc('blockwtce\'d {}.'.format(
		targets[0].char_name))


@mod_only()
def ooc_cmd_unblockwtce(client, arg):
	"""
	Allow a user to use WT/CE again.
	Usage: /unblockwtce <id>
	"""
	if len(arg) == 0:
		raise ArgumentError(
			'You must specify a target. Use /unblockwtce <id>.')
	try:
		targets = client.server.client_manager.get_targets(
			client, TargetType.ID, int(arg), False)
	except:
		raise ArgumentError('You must enter a number. Use /unblockwtce <id>.')
	if not targets:
		raise ArgumentError('Target not found. Use /unblockwtce <id>.')
	for target in targets:
		target.can_wtce = True
		target.send_ooc(
			'A moderator unblocked you from using judge signs.')
		database.log_room('unblockwtce', client, client.area, target=target)
	client.send_ooc('unblockwtce\'d {}.'.format(
		targets[0].char_name))


@mod_only()
def ooc_cmd_judgelog(client, arg):
	"""
	List the last 10 uses of judge controls in the current area.
	Usage: /judgelog
	"""
	if len(arg) != 0:
		raise ArgumentError('This command does not take any arguments.')
	jlog = client.area.judgelog
	if len(jlog) > 0:
		jlog_msg = '== Judge Log =='
		for x in jlog:
			jlog_msg += f'\r\n{x}'
		client.send_ooc(jlog_msg)
	else:
		raise ServerError(
			'There have been no judge actions in this area since start of session.'
		)

def ooc_cmd_afk(client, arg):
	client.server.client_manager.toggle_afk(client)
