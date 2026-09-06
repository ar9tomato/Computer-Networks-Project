import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

class VDNNetwork(nn.Module):
    def __init__(self, state_dim, action_dim):
        super(VDNNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, 128)
        self.fc2 = nn.Linear(128, 128)
        self.out = nn.Linear(128, action_dim)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        return self.out(x)

class MADRLEAURP:
    def __init__(self, network, metrics):
        self.net = network
        self.metrics = metrics
        
        self.num_nodes = network.num_nodes
        self.state_dim = 2 + self.num_nodes
        self.action_dim = self.num_nodes
        
        self.device = torch.device("cpu")
        
        self.q_net = VDNNetwork(self.state_dim, self.action_dim).to(self.device)
        self.target_net = VDNNetwork(self.state_dim, self.action_dim).to(self.device)
        self.target_net.load_state_dict(self.q_net.state_dict())
        self.optimizer = optim.Adam(self.q_net.parameters(), lr=0.001)
        
        self.epsilon = 1.0
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.05
        self.gamma = 0.99

    def execute_gossip_protocol(self):
        for node in self.net.nodes:
            if not node.is_alive(): continue
            
            uncertainties = {n: 1.0 - 2*abs(node.trust_table[n] - 0.5) for n in node.neighbors_1hop}
            sorted_uncertainties = sorted(uncertainties.items(), key=lambda x: x[1], reverse=True)[:3]
            top_3_nodes = [x[0] for x in sorted_uncertainties]
            
            targets = set(node.neighbors_1hop + node.neighbors_2hop)
            for target_id in targets:
                target = self.net.nodes[target_id]
                if target.group_id == node.group_id and target.is_alive():
                    self.metrics.gossip_messages += len(top_3_nodes)
                    self.metrics.pt_gid_broadcasts += 1
                    
                    for un_node in top_3_nodes:
                        target.trust_table[un_node] = 0.8 * target.trust_table[un_node] + 0.2 * node.trust_table[un_node]

    def get_actions(self, states, epsilon_override=None):
        eps = epsilon_override if epsilon_override is not None else self.epsilon
        actions = []
        state_tensor = torch.FloatTensor(np.array(states)).to(self.device)
        with torch.no_grad():
            q_values = self.q_net(state_tensor).cpu().numpy()
            
        for i, node in enumerate(self.net.nodes):
            valid_actions = node.neighbors_1hop + [node.node_id]
            if not node.is_alive() or len(valid_actions) == 0:
                actions.append(node.node_id)
                continue
                
            if np.random.rand() < eps:
                actions.append(np.random.choice(valid_actions))
            else:
                q = q_values[i].copy()
                mask = np.ones(self.action_dim, dtype=bool)
                mask[valid_actions] = False
                q[mask] = -1e9
                actions.append(np.argmax(q))
        return actions

    def train_step(self, states, actions, global_reward, next_states):
        states_t = torch.FloatTensor(np.array(states)).to(self.device)
        next_states_t = torch.FloatTensor(np.array(next_states)).to(self.device)
        actions_t = torch.LongTensor(actions).unsqueeze(1).to(self.device)
        reward_t = torch.FloatTensor([global_reward]).to(self.device)
        
        q_vals = self.q_net(states_t).gather(1, actions_t).sum()
        
        with torch.no_grad():
            next_q = self.target_net(next_states_t)
            max_next_q = next_q.max(1)[0].sum()
            target_q = reward_t + self.gamma * max_next_q
            
        loss = nn.MSELoss()(q_vals, target_q)
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

    def step_environment(self, training=True):
        self.metrics.simulation_time += 1
        states = [n.get_local_state(self.num_nodes) for n in self.net.nodes]
        
        for _ in range(5):
            src = np.random.randint(self.num_nodes)
            dst = np.random.randint(self.num_nodes)
            if src != dst and self.net.nodes[src].is_alive():
                packet = {'dst': dst, 'delay': 0}
                if len(self.net.nodes[src].buffer) < self.net.nodes[src].buffer_capacity:
                    self.net.nodes[src].buffer.append(packet)
                    self.metrics.packets_generated += 1
                else:
                    self.metrics.packets_dropped += 1

        actions = self.get_actions(states, epsilon_override=None if training else 0.0)
        
        step_delivery_reward = 0
        step_drop_penalty = 0
        step_delay_penalty = 0

        for i, node in enumerate(self.net.nodes):
            if not node.is_alive() or len(node.buffer) == 0: continue
            
            packet = node.buffer.pop(0)
            packet['delay'] += 1
            action = actions[i]
            
            node.consume_energy(0.1)
            
            if action == packet['dst']:
                self.metrics.packets_delivered += 1
                self.metrics.total_delay += packet['delay']
                step_delivery_reward += 10.0
                node.trust_table[action] = min(1.0, node.trust_table[action] + 0.1)
            elif action == i:
                if len(node.buffer) < node.buffer_capacity:
                    node.buffer.append(packet)
                    step_delay_penalty += 0.1
                else:
                    self.metrics.packets_dropped += 1
                    step_drop_penalty += 2.0
            else:
                target = self.net.nodes[action]
                if target.receive_packet(packet):
                    node.trust_table[action] = min(1.0, node.trust_table[action] + 0.05)
                else:
                    self.metrics.packets_dropped += 1
                    step_drop_penalty += 2.0
                    node.trust_table[action] = max(0.0, node.trust_table[action] - 0.2)

        self.execute_gossip_protocol()
        
        fairness = self.metrics.calculate_jains_fairness(self.net.nodes)
        energy_penalty = sum(100.0 - n.energy for n in self.net.nodes) * 0.001
        
        global_reward = step_delivery_reward - step_drop_penalty - step_delay_penalty - energy_penalty + (fairness * 5.0)
        next_states = [n.get_local_state(self.num_nodes) for n in self.net.nodes]
        
        if training:
            self.train_step(states, actions, global_reward, next_states)
            
        if self.metrics.simulation_time % 50 == 0:
            self.target_net.load_state_dict(self.q_net.state_dict())
