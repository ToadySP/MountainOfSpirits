import random
import re
import time
import threading
import asyncio
import arrow
import datetime
import pytimeparse

from server import database
from server.party import Party, Vote
from server.constants import TargetType
from server.exceptions import ClientError, ServerError, ArgumentError

from . import mod_only

__all__ = [
	'ooc_cmd_roll',
	'ooc_cmd_rollp',
	'ooc_cmd_notecard',
	'ooc_cmd_notecardclear',
	'ooc_cmd_notecardreveal',
	'ooc_cmd_rollareload',
	'ooc_cmd_rollaset',
	'ooc_cmd_rolla',
	'ooc_cmd_coinflip',
	'ooc_cmd_8ball',
	'ooc_cmd_nat20',
	'ooc_cmd_autopass',
	'ooc_cmd_follow',
	'ooc_cmd_unfollow',
	'ooc_cmd_followers',
	'ooc_cmd_followable',
	'ooc_cmd_hostage',
	'ooc_cmd_time',
	'ooc_cmd_timer',
	'ooc_cmd_setalarm',
	'ooc_cmd_setalarmsecs',
	'ooc_cmd_setalarmhours',
	'ooc_cmd_party',
	'ooc_cmd_parties',
	'ooc_cmd_partyinvite',
	'ooc_cmd_createparty',
	'ooc_cmd_lockparty',
	'ooc_cmd_unlockparty',
	'ooc_cmd_joinparty',
	'ooc_cmd_leaveparty',
	'ooc_cmd_destroyparty',
	'ooc_cmd_partykick',
	'ooc_cmd_startmgvote',
	'ooc_cmd_revealmgvote',
	'ooc_cmd_mgvote',
	'ooc_cmd_mgroles',
	'ooc_cmd_mgvp',
	'ooc_cmd_clearroles',
	'ooc_cmd_hide',
	'ooc_cmd_unhide',
	'ooc_cmd_rolesvisible',
	'ooc_cmd_addrole',
	'ooc_cmd_broadcast'
]

def ooc_cmd_addrole(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if not client.is_mod and client.party.leader != client:
		raise ClientError('You are not the party leader.')
	if len(arg) == 0:
		raise ArgumentError('Too many arguments! Use /addrole [id] [role].')
	else:
		arg = arg.split()
		try:
			id = int(arg[0])
		except:
			raise ArgumentError('Given ID does not look like a valid ID.')
	if len(arg) < 2:
		raise ArgumentError('Not enough arguments! Use /addrole [id] [role].')
	party = client.party
	for member in party.users:
		if member.id == id:
			member.partyrole = arg[1]
			member.votepower = 0
			member.send_ooc(f'Your role is now {member.partyrole}')
			client.send_ooc(f'Assigned {arg[1]} to {member.name}.')
			return
	raise ArgumentError(f'{id} does not look like a valid ID.')

def ooc_cmd_rolesvisible(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if client.party.leader != client:
		raise ClientError('You are not the party leader.')
	if len(arg) > 0:
		raise ArgumentError('Too many arguments.')
	if client.party.rolesvisible:
		client.party.rolesvisible = False
		for member in client.party.users:
			member.send_ooc('Party roles are no longer visible.')
	else:
		client.party.rolesvisible = True
		for member in client.party.users:
			member.send_ooc('Party roles are now visible.')

def ooc_cmd_hide(client, arg):
	if client not in client.area.owners and not client.is_mod:
		raise ClientError('You must be a CM.')
	if not arg:
		raise ClientError('You must specify a target. Use /hide <id>.')
	if not client.area.is_hub and not client.area.sub:
		raise ClientError('Must be in a hub to hide.')
	if client.area.is_hub:
		if client.area.hubtype == 'user':
			raise ClientError('Cannot hide in this hub.')
	if client.area.sub:
		if client.area.hub.hubtype == 'user':
			raise ClientError('Cannot hide in this hub.')
	if arg == '*':
		targets = [c for c in client.area.clients if c != client and c != client.area.owners]
	else:
		targets = None
		arg = arg.split()
	if len(arg) > 1:
		raise ArgumentError('Too many arguments, use one ID.')
	if targets is None:
		try:
			targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg[0]), False)
			for c in targets:
				if client not in c.area.owners and not client.is_mod:
					raise ArgumentError('That client is not in an area you own!')
				client.send_ooc(f'Hiding {c.char_name}.')
				c.hidden = True
				c.send_ooc('You are now hidden')
		except:
			raise ClientError('That doesn\'t look like a valid ID.')
	elif targets:
		try:
			for c in targets:
				if client not in c.area.owners and not client.is_mod:
					client.send_ooc(f'{c.char_name} is not in an area you own!')	
				else:
					client.send_ooc('Hiding {c.char_name}.')
					c.hidden = True
					c.send_ooc('You are now hidden')
		except:
			raise ClientError('Error while trying to hide all players.')

def ooc_cmd_unhide(client, arg):
	if len(arg) == 0 and client.hidden:
		client.hidden = False
		client.send_ooc('You are no longer hidden')
		return
	elif len(arg) == 0 and not client.hidden:
		raise ClientError('You are not hidden.')
	elif arg[0] == '*':
		targets = [c for c in client.area.clients if c != client and c != client.area.owners]
	else:
		targets = None
		arg = arg.split()
	if len(arg) > 1:
		raise ArgumentError('Too many arguments, use one ID.')
	if targets is None:
		try:
			targets = client.server.client_manager.get_targets(client, TargetType.ID, int(arg[0]), False)
			for c in targets:
				if client not in c.area.owners:
					raise ArgumentError('That client is not in an area you own!')
				client.send_ooc(f'unhiding {c.char_name}.')
				c.hidden = False
				c.send_ooc('You no longer hidden')
		except:
			raise ClientError('That doesn\'t look like a valid ID.')
	elif targets:
		try:
			for c in targets:
				if client not in c.area.owners:
					raise ArgumentError('That client is not in an area you own!')
				client.send_ooc(f'unhiding {c.char_name}.')
				c.hidden = False
				c.send_ooc('You are no longer hidden')
		except:
			raise ClientError('Error while trying to hide all players.')


def ooc_cmd_mgvote(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if len(client.party.votes) == 0:
		raise ClientError('No ongoing vote.')
	if len(arg) == 0:
		if client.party.leader == client:
			msg = 'Party Vote:'
			for vote in client.party.votes:
				msg += f'\n{vote.name}: {vote.number} vote(s).'
			client.send_ooc(msg)
			return
	if client.votepower < 0:
		raise ClientError('You can\'t vote again.')
	for vote in client.party.votes:
		if vote.name == arg:
			vote.number += 1
			client.votepower -= 1
			vote.voters.add(client)
			client.send_ooc(f'Voted for {arg}.')
			client.party.leader.send_ooc(f'{client.char_name} voted for {arg}.')
			return
	raise ArgumentError('Invalid argument.')

def ooc_cmd_mgvp(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if len(arg) == 0:
		raise ArgumentError('Not enough arguments.')
	args = arg.split()
	id = int(args[0])
	if len(args) == 1:
		for user in client.party.users:
			if user.partyrole != '':
				client.send_ooc(f'{user.name}\'s vote power is {user.votepower}.')
	elif len(args) == 2:
		if args[1] == '+':
			for user in client.party.users:
				if user.id == id:
					user.votepower += 1
					client.send_ooc('{user.name}\s vote power has been increased by one.')
					return
		elif args[1] == '-':
			for user in client.party.users:
				if user.id == id:
					user.votepower -= 1
					client.send_ooc('{user.name}\s vote power has been decreased by one.')
					return
	else:
		raise ArgumentError('Too many arguments. Use /mgvp <id> <+ or -> or /mgvp <id>.')

def ooc_cmd_revealmgvote(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if len(client.party.votes) == 0:
		raise ClientError('No ongoing vote.')
	msg = 'Party Vote:'
	for vote in client.party.votes:
		msg += f'\n{vote.name}: {vote.number} vote(s).'
	client.party.votes = set()
	client.area.broadcast_ooc(msg)
	for user in client.party.users:
		user.send_ooc(msg)
		if user.partyrole == 'Sacrifice':
			user.votepower = 1
		else:
			user.votepower = 0

def ooc_cmd_startmgvote(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if client.party.leader != client and not client.is_mod:
		raise ClientError('You are not the party leader.')
	if len(arg) == 0:
		raise ArgumentError('Not enough arguments, use /startpvote <arguments>.')
	args = arg.split()
	party = client.party
	party.votes = set()
	msg = 'Vote started with arguments: '
	for a in args:
		vote = Vote(a)
		party.votes.add(vote)
		msg += f'"{a}" '
	for user in party.users:
		user.send_ooc(msg)
		if user.partyrole == 'Sacrifice':
			user.votepower = 1
		else:
			user.votepower = 0

def ooc_cmd_clearroles(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if client.party.leader != client:
		raise ClientError('You are not the party leader.')
	for user in client.party.users:
		user.partyrole = ''
		user.votepower = 0

def ooc_cmd_mgroles(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if client.party.leader != client:
		raise ClientError('You are not the party leader.')
	for user in client.party.users:
		user.partyrole = ''
		user.votepower = 0
	if len(arg) == 0:
		if len(client.party.users) < 5:
			raise ArgumentError('Not enough players to hand out the roles!')
		else:
			client.send_ooc(client.party.mg_roles(arg))
			for user in client.party.users:
				if user.partyrole != '':
					user.send_ooc(f'Your role is now {user.partyrole}.')
	else:
		args = arg.split()
		check = 5 + len(args)
		if len(client.party.users) < check:
			raise ArgumentError('Not enough players to hand out the roles!')
		client.send_ooc(client.party.mg_roles(args))
		for user in client.party.users:
			if user.partyrole != '':
			   user.send_ooc(f'Your role is now {user.partyrole}.')

def ooc_cmd_party(client, arg):
	if len(arg) > 0:
		raise ArgumentError('This command takes no arguments.')
	if not client.in_party:
		ooc_cmd_parties(client, arg)
	else:
		party = client.party
		users = party.users
		msg = f'Party Members: {len(users)}\n=== {party.name} ==='
		if party.leader not in users:
			for member in users:
				if party.leader not in users:
					party.leader = member
					member.send_ooc('Party Leader left, you are now the new Party Leader.')
			else:
					member.send_ooc(f'Party Leader left, {party.leader.name} is the new Party Leader.')
		for member in users:
			msg += f'\n[{member.area.name}][{member.id}] {member.char_name}: {member.name}'
			if party.leader == member:
				msg += ' (Party Leader)'
			if party.rolesvisible:
				if member.partyrole != '':
					msg += f' ({member.partyrole})'
			elif party.leader == client:
				if member.partyrole != '':
					msg += f' ({member.partyrole})'
			elif member == client and member != party.leader:
				if member.partyrole != '':
					msg += f' ({member.partyrole})'
		client.send_ooc(msg)

def ooc_cmd_parties(client, arg):	
	if len(arg) > 0:
		raise ArgumentError('This command takes no arguments.')			
	if len(client.server.parties) != 0:
		msg = 'Current parties:'
		parties = client.server.parties
		for party in parties:
			if len(party.users) == 0:
				client.server.parties.remove(party)
				if len(client.server.parties) == 0:
					raise ClientError('No parties currently on the server.')
			if party.leader not in party.users:
				for member in party.users:
					if party.leader not in party.users:
						party.leader = member
						member.send_ooc('Party Leader left, you are now the new Party Leader.')
					else:
						member.send_ooc(f'Party Leader left, {party.leader.name} is the new Party Leader.')
			if party.lock:
				lock = 'Private'
			else:
				lock = 'Public'
			msg += f'\n===================\n[{party.id}] {party.name} [{len(party.users)} Members][{lock}]'
			msg += f'\nParty Leader: [{party.leader.id}] {party.leader.char_name}.'
		msg += '\n==================='
		client.send_ooc(msg)
	else:
		raise ClientError('No parties currently on the server.')

def ooc_cmd_lockparty(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if client.party.leader != client:
		raise ClientError('You are not the party leader.')
	if client.party.lock:
		raise ArgumentError('This party is already private.')
	client.party.lock = True
	client.send_ooc(f'{client.party.name} is now private.')

def ooc_cmd_unlockparty(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if client.party.leader != client:
		raise ClientError('You are not the party leader.')
	if not client.party.lock:
		raise ArgumentError('This party is already public.')
	client.party.lock = False
	client.send_ooc(f'{client.party.name} is now public.')

def ooc_cmd_destroyparty(client, arg):
	if not client.in_party and not client.is_mod:
		raise ClientError('You aren\'t in a party.')
	if not client.is_mod and client.party.leader != client:
		raise ClientError('You are not the party leader.')
	if len(arg) == 0:
		partyusers = set()
		party = client.party
		for member in client.party.users:
			partyusers.add(member)
		for member in partyusers:
			client.party.users.remove(member)
			member.party = None
			member.in_party = False
			member.partyrole = ''
			member.votepower = 0
			member.send_ooc(f'Party Leader destroyed party!')
		client.server.parties.remove(party)
	elif client.is_mod:
		try:
			id = int(arg)
		except:
			raise ArgumentError('Given ID does not look like a valid ID.')
		for party in client.server.parties:
			parties = []
			parties.add(party)
		for party in parties:
			if id == party.id:
				partyusers = set()
				for member in client.party.users:
					partyusers.add(member)
				for member in partyusers:
					client.party.users.remove(member)
					member.party = None
					member.in_party = False
					member.partyrole = ''
					member.votepower = 0
					member.send_ooc('Party was destroyed!')
				client.server.parties.remove(party)
				return
		raise ArgumentError(f'{arg} does not look like a valid party ID.')
	else:
		raise ArgumentError('Too many arguments.')

def ooc_cmd_joinparty(client, arg):
	if client.in_party:
		raise ClientError('You are already in a party!')
	else:
		try:
			id = int(arg)
		except:
			raise ArgumentError('Given ID does not look like a valid ID.')
		for party in client.server.parties:
			if id == party.id:
				if party.lock:
					if not client.is_mod and client.id not in party.invite_list:
						raise ClientError('Group is private!')
					else:
						for user in party.users:
							user.send_ooc(f'{client.name} joined {party.name}.')
						party.add_user(client)
						client.party = party
						client.in_party = True
						client.send_ooc(f'Joined {party.name}.')
						return
				else:
					for user in party.users:
						user.send_ooc(f'{client.name} joined {party.name}.')
					party.add_user(client)
					client.party = party
					client.in_party = True
					client.send_ooc(f'Joined {party.name}.')
					return
		raise ArgumentError(f'{arg} does not look like a valid ID.')

def ooc_cmd_leaveparty(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	party = client.party
	party.users.remove(client)
	client.party = None
	client.in_party = False
	client.partyrole = ''
	client.votepower = 0
	if len(party.users) != 0:
		client.send_ooc(f'Left {party.name}.')
		if party.leader == client:
			for member in party.users:
				if party.leader not in party.users:
					party.leader = member
					member.send_ooc('Party Leader left, you are now the new Party Leader.')
				else:
					member.send_ooc(f'Party Leader left, {party.leader.name} is the new Party Leader.')
	else:
		client.server.parties.remove(party)
		client.send_ooc(f'Left {party.name}. Party was destroyed.')

def ooc_cmd_partykick(client, arg):
	if not client.in_party:
		raise ClientError('You aren\'t in a party.')
	if not client.is_mod and client.party.leader != client:
		raise ClientError('You are not the party leader.')
	else:
		try:
			id = int(arg)
		except:
			raise ArgumentError('Given ID does not look like a valid ID.')
	party = client.party
	users = set()
	for member in party.users:
		users.add(member)
	for member in users:
		if member.id == id:
			client.party.users.remove(member)
			member.party = None
			member.in_party = False
			member.partyrole = ''
			member.votepower = 0
			member.send_ooc('You were kicked from the party!')
			client.send_ooc(f'Kicked {member.name} from the party.')
			return
	raise ArgumentError(f'{id} does not look like a valid ID.')
	

def ooc_cmd_createparty(client, arg):
	if client.in_party:
		raise ClientError('You are already in a party!')
	if len(arg) == 0:
		raise ArgumentError('Not enough arguments, use /createparty <name>.')
	if len(arg) > 32:
		raise ArgumentError('That name is too long!')
	id = len(client.server.parties)
	client.party = Party(client.server, arg, client, id)
	client.server.parties.append(client.party)
	client.in_party = True
	client.send_ooc(f'Created party {client.party.name}.')

def ooc_cmd_partyinvite(client, arg):
	if not arg:
		raise ClientError('You must specify a target. Use /partyinvite <id>')
	elif not client.in_party:
		raise ClientError('You aren\'t in a party.')
	elif client.party.leader != client:
		raise ClientError('You are not the party leader, ask them to invite.')
	try:
		c = client.server.client_manager.get_targets(client, TargetType.ID,int(arg), False)[0]
		client.party.invite_list[c.id] = None
		client.send_ooc('{} is invited to your group.'.format(c.char_name))
		c.send_ooc(f'You were invited and given access to {client.party.name}.')
	except:
		raise ClientError('You must specify a target. Use /partyinvite <id>')

def ooc_cmd_time(client, arg):
	if len(arg) > 0:
		raise ArgumentError('This command takes no arguments')
	msg = 'The current time is:\n['
	msg += time.asctime(time.localtime(time.time()))
	msg += ']'
	client.send_ooc(msg)

def ooc_cmd_setalarm(client, arg):
	if len(arg) == 0:
		raise ArgumentError('Not enough arguments. Use /settimer <minutes>')
	time = int(arg)
	send = time
	time = time * 60
	if time > 43200:
		raise ArgumentError('Can\'t set a time longer than 12 hours.')
	client.timer.setalarm(time, 'minutes', client)
	client.send_ooc(f'Alarm set for {arg} minutes from now.')

def ooc_cmd_setalarmsecs(client, arg):
	if len(arg) == 0:
		raise ArgumentError('Not enough arguments. Use /settimer <minutes>')
	time = int(arg)
	if time > 43200:
		raise ArgumentError('Can\'t set a time longer than 12 hours.')
	client.timer.setalarm(time, 'seconds', client)
	client.send_ooc(f'Alarm set for {arg} seconds from now.')

def ooc_cmd_setalarmhours(client, arg):
	if len(arg) == 0:
		raise ArgumentError('Not enough arguments. Use /settimer <minutes>')
	time = int(arg)
	send = time
	time = time * 3600
	if time > 43200:
		raise ArgumentError('Can\'t set a time longer than 12 hours.')
	client.timer.setalarm(time, 'hours', client)
	client.send_ooc(f'Alarm set for {arg} hours from now.')

def ooc_cmd_follow(client, arg):
	if len(arg) == 0:
		if client.is_following == False:
			raise ArgumentError('You are not following anyone, please use /follow <id> first.')
		else:
			for c in client.following:
				client.send_ooc(f'You are currently following {c.char_name}.')
			return
	if client.is_following == True:
		raise ClientError('You are already following someone.')
	if len(arg) > 1:
		arg = arg.split(' ')
	for id in arg:
		try:
			id = int(id)
			c = client.server.client_manager.get_targets(client, TargetType.ID, id, False)[0]
		except:
			raise ArgumentError(f'{id} does not look like a valid ID.')
		if not c in client.area.clients:
			raise ArgumentError('You can only follow people when they are in the area.')
		if c == client:
			raise ArgumentError('You cannot follow yourself.')
		if c.followable == False:
			raise ClientError('That person is not followable.')
		else:
			client.following.clear()
			client.is_following = True
			client.following.append(c)
			c.followers.append(client)
			c.send_ooc(f'{client.char_name} is now following you.')
			client.send_ooc(f'You are now following {c.char_name}.')

def ooc_cmd_hostage(client, arg):
	if client.is_mod == False:
		raise ClientError('You must be authorized to do this.')
	if len(arg) == 0:
		raise ArgumentError('You must specify an ID to take someone hostage.')
	if len(arg) > 1:
		arg = arg.split(' ')
	for id in arg:
		try:
			id = int(id)
			c = client.server.client_manager.get_targets(client, TargetType.ID, id, False)[0]
		except:
			raise ArgumentError(f'{id} does not look like a valid ID.')
		if not c in client.area.clients:
			raise ArgumentError('You can only take people hostage when they are in the area.')
		if c == client:
			raise ArgumentError('You cannot take yourself hostage.')
		if c.is_hostage == True:
			for cc in client.followers:
				if cc == c:
					c.following.remove(client)
					client.followers.remove(c)
					c.is_following = False
					c.is_hostage = False
					c.send_ooc(f'{client.char_name} is no longer taking you hostage.')
					client.send_ooc(f'{c.char_name} is no longer your hostage, they are free to move around.')
					return
			raise ClientError(f'{c.char_name} is already taken hostage by someone else!')
		else:
			msg = f'You have been taken hostage by {client.char_name}!'
			if c.is_following == True:
				c.is_following = False
				for cc in c.following:
					cc.followers.remove(c)
					cc.send_ooc(f'{c.char_name} has been taken hostage by someone and is no longer following you!')
					c.following.remove(cc)
					msg += f' No longer following {cc.char_name}.'
			c.following.append(client)
			client.followers.append(c)
			c.is_following = True
			c.is_hostage = True
			c.send_ooc(msg)
			client.send_ooc(f'You have taken {c.char_name} hostage, they are forced to follow you.')

def ooc_cmd_unfollow(client, arg):
	if len(arg) > 0:
		raise ArgumentError('This commands takes no arguments.')
	if client.is_following == False:
		raise ClientError('You are not following anyone.')
	if client.is_hostage:
		raise ClientError('You cannot unfollow because you are a hostage.')
	else:
		client.is_following = False
		for c in client.following:
			c.send_ooc(f'{client.char_name} is no longer following you.')
			c.followers.remove(client)
			client.send_ooc(f'You unfollowed {c.char_name}.')
			client.following.clear()

def ooc_cmd_followers(client, arg):
	if len(arg) > 0:
		raise ArgumentError('This commands takes no arguments.')
	if len(client.followers) == 0:
		raise ClientError('No one is following you.')
	msg = 'Followers:'
	for c in client.followers:
		msg += f'\n{c.char_name}'
		if c.is_hostage == True:
			msg += ' [Hostage]'
		if len(c.followers) > 0:
			msg += ' ('
			index = 0
			prev_index = index
			for cc in c.followers:
				if index != prev_index:
					msg += ', '
				msg += f'{cc.char_name}'
				if len(cc.followers) > 0:
					msg += '('
					c_index = 0
					c_prev_index = index
					for ccc in cc.followers:
						if c_index != c_prev_index:
							msg += ', '
						msg += f'{ccc.char_name}'
						if len(ccc.followers) > 0:
							msg += '('
							cc_index = 0
							cc_prev_index = index
							for cccc in ccc.followers:
								if c_index != c_prev_index:
									msg += ', '
								msg += f'{cccc.char_name}'
								cc_prev_index = c_index
								cc_index += 1
							msg += ')'
					msg += ')'
				prev_index = index
				index += 1
			msg += ')'
	msg += '.'
	client.send_ooc(msg)

def ooc_cmd_followable(client, arg):
	if client.followable == True:
		if len(arg) > 0:
			if arg == 'new':
				client.followable = False
				client.send_ooc('You are no longer followable, but you retain your current followers.')
			else:
				raise ArgumentError('This command only takes "new" or nothing as argument.')
		else:
			for c in client.followers:
				c.following.remove(client)
				c.send_ooc(f'{client.char_name} is no longer followable. Unfollowing.')
				c.is_following = False
			client.followers.clear()
			client.followable = False
			client.send_ooc('You are no longer followable, and all your followers were cleared.')
	else:
		client.followable = True
		client.send_ooc('You are now followable.')

def ooc_cmd_roll(client, arg):
	"""
	Roll a die. The result is shown publicly.
	Usage: /roll [max value] [rolls]
	"""
	roll_max = 11037
	if len(arg) != 0:
		try:
			val = list(map(int, arg.split(' ')))
			if not 1 <= val[0] <= roll_max:
				raise ArgumentError(
					f'Roll value must be between 1 and {roll_max}.')
		except ValueError:
			raise ArgumentError(
				'Wrong argument. Use /roll [<max>] [<num of rolls>]')
	else:
		val = [6]
	if len(val) == 1:
		val.append(1)
	if len(val) > 2:
		raise ArgumentError(
			'Too many arguments. Use /roll [<max>] [<num of rolls>]')
	if val[1] > 20 or val[1] < 1:
		raise ArgumentError('Num of rolls must be between 1 and 20')
	roll = ''
	for _ in range(val[1]):
		roll += str(random.randint(1, val[0])) + ', '
	roll = roll[:-2]
	if val[1] > 1:
		roll = '(' + roll + ')'
	if client.char_name.startswith('custom') and client.showname != 0:
		client.area.broadcast_ooc('{} rolled {} out of {}.'.format(client.showname, roll, val[0]))
	else:
		client.area.broadcast_ooc('{} rolled {} out of {}.'.format(client.char_name, roll, val[0]))
	database.log_room('roll', client, client.area, message=f'{roll} out of {val[0]}')


def ooc_cmd_rollp(client, arg):
	"""
	Roll a die privately.
	Usage: /roll [max value] [rolls]
	"""
	roll_max = 11037
	if len(arg) != 0:
		try:
			val = list(map(int, arg.split(' ')))
			if not 1 <= val[0] <= roll_max:
				raise ArgumentError(
					f'Roll value must be between 1 and {roll_max}.')
		except ValueError:
			raise ArgumentError(
				'Wrong argument. Use /rollp [<max>] [<num of rolls>]')
	else:
		val = [6]
	if len(val) == 1:
		val.append(1)
	if len(val) > 2:
		raise ArgumentError(
			'Too many arguments. Use /rollp [<max>] [<num of rolls>]')
	if val[1] > 20 or val[1] < 1:
		raise ArgumentError('Num of rolls must be between 1 and 20')
	roll = ''
	for _ in range(val[1]):
		roll += str(random.randint(1, val[0])) + ', '
	roll = roll[:-2]
	if val[1] > 1:
		roll = '(' + roll + ')'
	if client.char_name.startswith('custom') and client.showname != 0:
		client.send_ooc('{} rolled {} out of {}.'.format(client.showname, roll, val[0]))
		client.area.broadcast_ooc('{} rolled in secret.'.format(client.showname))
	else:
		client.send_ooc('{} rolled {} out of {}.'.format(client.char_name, roll, val[0]))
		client.area.broadcast_ooc('{} rolled in secret.'.format(client.char_name))
	
	for c in client.area.owners:
		c.send_ooc('[{}]{} secretly rolled {} out of {}.'.format(client.area.abbreviation, client.char_name, roll, val[0]))

	database.log_room('rollp', client, client.area, message=f'{roll} out of {val[0]}')


def ooc_cmd_notecard(client, arg):
	"""
	Write a notecard that can only be revealed by a CM.
	Usage: /notecard <message>
	"""
	if len(arg) == 0:
		raise ArgumentError('You must specify the contents of the note card.')
	client.area.cards[client.char_name] = arg
	client.area.broadcast_ooc('{} wrote a note card.'.format(
		client.char_name))
	database.log_room('notecard', client, client.area)


def ooc_cmd_notecardclear(client, arg):
	"""
	Erase a notecard.
	Usage: /notecard_clear
	"""
	try:
		del client.area.cards[client.char_name]
		client.area.broadcast_ooc('{} erased their note card.'.format(
			client.char_name))
		database.log_room('notecard_erase', client, client.area)
	except KeyError:
		raise ClientError('You do not have a note card.')


def ooc_cmd_notecardreveal(client, arg):
	"""
	Reveal all notecards and their owners.
	Usage: /notecard_reveal
	"""
	if not client in client.area.owners:
		raise ClientError('Only CM can reveal notecards.')
	if len(client.area.cards) == 0:
		raise ClientError('There are no cards to reveal in this area.')
	msg = 'Note cards have been revealed.\n'
	for card_owner, card_msg in client.area.cards.items():
		msg += f'{card_owner}: {card_msg}\n'
	client.area.cards.clear()
	client.area.broadcast_ooc(msg)
	database.log_room('notecard_reveal', client, client.area)


@mod_only()
def ooc_cmd_rollareload(client, arg):
	"""
	Reload ability dice sets from a configuration file.
	Usage: /rolla_reload
	"""
	rolla_reload(client.area)
	client.send_ooc('Reloaded ability dice configuration.')
	database.log_room('rolla_reload', client, client.area)


def rolla_reload(area):
	try:
		import yaml
		with open('config/dice.yaml', 'r') as dice:
			area.ability_dice = yaml.safe_load(dice)
	except:
		raise ServerError(
			'There was an error parsing the ability dice configuration. Check your syntax.'
		)


def ooc_cmd_rollaset(client, arg):
	"""
	Choose the set of ability dice to roll.
	Usage: /rolla_set <name>
	"""
	if not hasattr(client.area, 'ability_dice'):
		rolla_reload(client.area)
	available_sets = ', '.join(client.area.ability_dice.keys())
	if len(arg) == 0:
		raise ArgumentError(
			f'You must specify the ability set name.\nAvailable sets: {available_sets}'
		)
	elif arg not in client.area.ability_dice:
		raise ArgumentError(
			f'Invalid ability set \'{arg}\'.\nAvailable sets: {available_sets}'
		)
	client.ability_dice_set = arg
	client.send_ooc(f"Set ability set to {arg}.")


def ooc_cmd_rolla(client, arg):
	"""
	Roll a specially labeled set of dice (ability dice).
	Usage: /rolla
	"""
	if not hasattr(client.area, 'ability_dice'):
		rolla_reload(client.area)
	if not hasattr(client, 'ability_dice_set'):
		raise ClientError(
			'You must set your ability set using /rolla_set <name>.')
	ability_dice = client.area.ability_dice[client.ability_dice_set]
	max_roll = ability_dice['max'] if 'max' in ability_dice else 6
	roll = random.randint(1, max_roll)
	ability = ability_dice[roll] if roll in ability_dice else "Nothing happens"
	if client.char_name.startswith('custom') and client.showname != 0:
		client.area.broadcast_ooc('{} rolled a {} (out of {}): {}.'.format(client.showname, roll, max_roll, ability))
	else:
		client.area.broadcast_ooc('{} rolled a {} (out of {}): {}.'.format(client.char_name, roll, max_roll, ability))
	database.log_room('rolla', client, client.area,
						message=f'{roll} out of {max_roll}: {ability}')


def ooc_cmd_coinflip(client, arg):
	"""
	Flip a coin. The result is shown publicly.
	Usage: /coinflip
	"""
	if len(arg) != 0:
		raise ArgumentError('This command has no arguments.')
	coin = ['heads', 'tails']
	flip = random.choice(coin)
	client.area.broadcast_ooc('{} flipped a coin and got {}.'.format(
		client.char_name, flip))
	database.log_room('coinflip', client, client.area, message=flip)

	
def ooc_cmd_8ball(client, arg):
	if len(arg) != 0:
		raise ArgumentError('This command has no arguments.')
	coin = ['yes', 'no', 'maybe', 'I dont know', 'perhaps', 'please do not', 'try again', 'you shouldn\'t ask that']
	flip = random.choice(coin)
	client.area.broadcast_ooc('The magic 8 ball says {}.'.format(flip))
	database.log_room('8ball', client, client.area)
	
@mod_only()
def ooc_cmd_nat20(client, arg):
	"""
	Roll a die. The result is shown publicly.
	Usage: /roll [max value] [rolls]
	"""
	if len(arg) != 0:
		raise ArgumentError(
				'This command takes no arguments')
	else:
		client.area.broadcast_ooc('{} rolled 20 out of 20.'.format(
			client.char_name))

@mod_only()
def ooc_cmd_broadcast(client, arg):
	"""
	Roll a die. The result is shown publicly.
	Usage: /roll [max value] [rolls]
	"""
	if len(arg) == 0:
		raise ArgumentError(
				'This command takes arguments')
	else:
		client.area.broadcast_ooc(arg)

def ooc_cmd_autopass(client, arg):
	"""
	Sends "pass" messages for the client automatically when changing areas.
	"""
	if len(arg) > 0:
		raise ArgumentError('This command takes no arguments.')
	if client.autopass == False:
		client.autopass = True
		client.send_ooc('Autopass enabled.')
	else:
		client.autopass = False
		client.send_ooc('Autopass disabled.')

def ooc_cmd_timer(client, arg):
	"""
	Manage a countdown timer in the current area. Note that timer of ID 0 is global.
	All other timer IDs are local to the area (valid IDs are 1 - 4).
	Usage:
	/timer <id> [+/-][time]
		Set the timer's time, optionally adding or subtracting time. If the timer had
		not been previously set up, it will be shown paused.
	/timer <id> start
	/timer <id> <pause|stop>
	/timer <id> hide
	"""

	arg = arg.split()
	if len(arg) < 1:
		msg = 'Currently active timers:'
		# Global timer
		timer = client.server.area_manager.timer
		if timer.set:
			if timer.started:
				msg += f'\nTimer 0 is at {timer.target - arrow.get()}'
			else:
				msg += f'\nTimer 0 is at {timer.static}'
		# Area timers
		for timer_id, timer in enumerate(client.area.timers):
			if timer.set:
				if timer.started:
					msg += f'\nTimer {timer_id+1} is at {timer.target - arrow.get()}'
				else:
					msg += f'\nTimer {timer_id+1} is at {timer.static}'
		client.send_ooc(msg)
		return

	# TI packet specification:
	# TI#TimerID#Type#Value#%
	# TimerID = from 0 to 4 (5 possible timers total)
	# Type 0 = start/resume/sync timer at time
	# Type 1 = pause timer at time
	# Type 2 = show timer
	# Type 3 = hide timer
	# Value = Time to set on the timer

	try:
		timer_id = int(arg[0])
	except:
		raise ArgumentError('Invalid ID. Usage: /timer <id>')

	if timer_id < 0 or timer_id > 4:
		raise ArgumentError('Invalid ID. Usage: /timer <id>')
	if timer_id == 0:
		timer = client.server.area_manager.timer
	else:
		timer = client.area.timers[timer_id-1]

	if len(arg) < 2:
		if timer.set:
			if timer.started:
				client.send_ooc(f'Timer {timer_id} is at {timer.target - arrow.get()}')
			else:
				client.send_ooc(f'Timer {timer_id} is at {timer.static}')
		else:
			client.send_ooc(f'Timer {timer_id} is unset.')
		return

	if client not in client.area.owners and not client.is_mod:
		raise ArgumentError('Only CMs or mods can modify timers. Usage: /timer <id>')
	if timer_id == 0 and not client.is_mod:
		raise ArgumentError('Only mods can set the global timer. Usage: /timer <id>')

	duration = pytimeparse.parse(''.join(arg[1:]))
	if duration is not None:
		if timer.set:
			if timer.started:
				if not (arg[1] == '+' or duration < 0):
					timer.target = arrow.get()
				timer.target = timer.target.shift(seconds=duration)
				timer.static = timer.target - arrow.get()
			else:
				if not (arg[1] == '+' or duration < 0):
					timer.static = datetime.timedelta(0)
				timer.static += datetime.timedelta(seconds=duration)
		else:
			timer.static = datetime.timedelta(seconds=abs(duration))
			timer.set = True
			if timer_id == 0:
				client.server.send_all_cmd_pred('TI', timer_id, 2)
			else:
				client.area.send_command('TI', timer_id, 2)

	if not timer.set:
		raise ArgumentError(f'Timer {timer_id} is not set in this area.')
	elif arg[1] == 'start':
		timer.target = timer.static + arrow.get()
		timer.started = True
		client.send_ooc(f'Starting timer {timer_id}.')
		database.log_room('timer.start', client, client.area, message=str(timer_id))
	elif arg[1] in ('pause', 'stop'):
		timer.static = timer.target - arrow.get()
		timer.started = False
		client.send_ooc(f'Stopping timer {timer_id}.')
		database.log_room('timer.stop', client, client.area, message=str(timer_id))
	elif arg[1] in ('unset', 'hide'):
		timer.set = False
		timer.started = False
		timer.static = None
		timer.target = None
		client.send_ooc(f'Timer {timer_id} unset and hidden.')
		database.log_room('timer.hide', client, client.area, message=str(timer_id))
		if timer_id == 0:
			client.server.send_all_cmd_pred('TI', timer_id, 3)
		else:
			client.area.send_command('TI', timer_id, 3)

	# Send static time if applicable
	if timer.set:
		s = int(not timer.started)
		static_time = int(timer.static.total_seconds()) * 1000

		if timer_id == 0:
			client.server.send_all_cmd_pred('TI', timer_id, s, static_time)
		else:
			client.area.send_command('TI', timer_id, s, static_time)

		client.send_ooc(f'Timer {timer_id} is at {timer.static}')

		target = client.area

		def timer_expired():
			if timer.schedule:
				timer.schedule.cancel()
			# Area was destroyed at some point
			if target is None or timer is None:
				return
			if timer_id != 0:
				target.send_ooc(f'Timer {timer_id} has expired.')
			timer.static = datetime.timedelta(0)
			timer.started = False
			database.log_room('timer.expired', None, target, message=str(timer_id))

		if timer.schedule:
			timer.schedule.cancel()
		if timer.started:
			timer.schedule = asyncio.get_event_loop().call_later(
				int(timer.static.total_seconds()), timer_expired)