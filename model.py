import torch
# torch.set_default_tensor_type('torch.cuda.FloatTensor')
import torch.nn as nn
import torch.nn.functional as F
from pytorchtreelstm.treelstm import TreeLSTM
import pytorchtreelstm.treelstm.util as TLUtil
class Model(torch.nn.Module):
    '''
    This model use h_c as a feature in h_a and h_b.
    '''
    def __init__(self, vocab_size, sort_vocab_size, emb_dim = 10, tree_dim = 10, out_dim = 3, use_c = True, use_const_emb = True, use_dot_product = True, device = torch.device('cuda')):
        super().__init__()
        print("VOCAB SIZE:", vocab_size)
        print("SORT SIZE", sort_vocab_size)
        print("USE C", use_c)
        print("USE CONSTANT EMB", use_const_emb)
        self.device = device
        self._emb_dim = emb_dim
        self._tree_dim = tree_dim
        self._use_c = use_c
        self._use_const_emb = use_const_emb
        self._use_dot_product = use_dot_product
        self.emb = nn.Embedding(vocab_size*2, emb_dim ).to(self.device) #*2 to handle out of vocab cases
        self.sort_emb = nn.Embedding(sort_vocab_size*2, emb_dim ).to(self.device)

        #calculate the input size of tree_lstm based on flags
        self.treelstm_input_size = emb_dim * 2
        if self._use_const_emb:
            self.treelstm_input_size += self._emb_dim
        if self._use_c:
            self.treelstm_input_size += self._tree_dim
        self.treelstm = TreeLSTM(self.treelstm_input_size, tree_dim).to(device)

        #calculate the size of the last layer before FNN
        self.next_to_last_size = tree_dim * 2
        if self._use_dot_product:
            self.next_to_last_size+=1

        self.fc1 = nn.Linear(self.next_to_last_size, tree_dim).to(self.device)
        self.fc2 = nn.Linear(tree_dim, out_dim).to(self.device)


    def metadata(self):
        return {"emb_dim": self._emb_dim,
                "tree_dim": self._tree_dim,
                "use_c": self._use_c,
                "use_const_emb": self._use_const_emb,
                "use_dot_product": self._use_dot_product,
                "model": "new_model"
        }

    def forward(self, cube, lit_a, lit_b):
        #if use context, need to compute context features first
        if self._use_c:
            h_c_raw, c_c_raw, c_sz = self.forward_a_tree(cube)
            h_c = TLUtil.stack_last_h(h_c_raw, c_sz)
            batch_size = h_c.shape[0]
            h_a_raw, c_a_raw, a_sz = self.forward_a_tree(lit_a, h_c)
            h_b_raw, c_b_raw, b_sz = self.forward_a_tree(lit_b, h_c)

        else:
            h_a_raw, c_a_raw, a_sz = self.forward_a_tree(lit_a)
            h_b_raw, c_b_raw, b_sz = self.forward_a_tree(lit_b)
        h_a = TLUtil.stack_last_h(h_a_raw, a_sz)
        h_b = TLUtil.stack_last_h(h_b_raw, b_sz)

        assert(h_a.shape[0] == h_b.shape[0])
        batch_size = h_a.shape[0]

        #compute the dot product here
        if self._use_dot_product:
            dotp = torch.diag(torch.matmul(h_a, torch.t(h_b)))
            dotp = dotp.view(batch_size, 1, -1)

        h_a = h_a.view(batch_size, 1, -1)
        h_b = h_b.view(batch_size, 1, -1)
        h = torch.cat((h_a, h_b), dim = -1)
        if self._use_dot_product:
            h = torch.cat((h, dotp), dim = -1)
        logits = self.fc2(F.relu(self.fc1(h)))
        if self.training:
            return logits.view(batch_size, -1)
        else:
            return logits.view(batch_size, -1), {
                "h_a_raw": h_a_raw,
                "h_b_raw": h_b_raw,
            }

    def forward_a_tree(self, tree, context_features = None):
        '''
        if context_features is not None, we are forwarding a L_a or L_b tree.
        if context_features is None, we are forwarding the C_tree.
        '''
        features = tree["features"].to(self.device)
        node_order = tree["node_order"].to(self.device)
        adjacency_list = tree["adjacency_list"].to(self.device)
        edge_order = tree["edge_order"].to(self.device)
        # print(features.shape)
        token_feat = features[:,0]
        sort_feat = features[:,1]

        # print("token_feat", token_feat.tolist())

        token_emb = self.emb(token_feat)
        sort_emb = self.sort_emb(sort_feat)
        # print(token_emb.shape)
        # print(const_emb.shape)
        if self._use_const_emb:
            const_emb = features[:, 2:2+self._emb_dim]*1.0
            const_emb = const_emb.to(self.device)
            features = torch.cat((token_emb, sort_emb, const_emb), dim = 1)
        else:
            features = torch.cat((token_emb, sort_emb), dim = 1)


        if context_features is None:
            if self._use_c:
                all_tiled_c = torch.zeros(features.shape[0], self._tree_dim).to(self.device)
                features = torch.cat((features, all_tiled_c), dim = 1)
        else:
            #tiling context features.
            tree_sizes = tree["tree_sizes"]
            batch_size = len(tree_sizes)
            # print(tree_sizes)
            assert(context_features.shape[0]==len(tree_sizes))
            assert(sum(tree_sizes) == features.shape[0])
            all_tiled_c = []
            for idx in range(len(tree_sizes)):
                tree_size = tree_sizes[idx]
                context_feat = context_features[idx]
                tiled_c = context_feat.repeat(tree_size, 1)
                all_tiled_c.append(tiled_c)
                # print("tiled_c.shape", tiled_c.shape)
            all_tiled_c = torch.cat(all_tiled_c, dim = 0)
            features = torch.cat((features, all_tiled_c), dim = 1)
            # print(all_tiled_c.shape)
        # features = token_emb
        h, c = self.treelstm(features, node_order, adjacency_list, edge_order)
        return h,c, tree["tree_sizes"] 
 
class OldModel(torch.nn.Module):
    '''
    The old model use h_c at the end (right before the FNN layer. h_c is concatenate with h_a and h_b)

    '''
    def __init__(self, vocab_size, sort_vocab_size, emb_dim = 10, tree_dim = 10, out_dim = 3, use_c = True, use_const_emb = True, use_dot_product = True, device = torch.device('cuda')):
        super().__init__()
        print("VOCAB SIZE:", vocab_size)
        print("SORT SIZE", sort_vocab_size)
        print("USE C", use_c)
        print("USE CONSTANT EMB", use_const_emb)
        self._emb_dim = emb_dim
        self._tree_dim = tree_dim
        self._use_c = use_c
        self._use_const_emb = use_const_emb
        self._use_dot_product = use_dot_product
        self.emb = nn.Embedding(vocab_size, emb_dim )
        self.sort_emb = nn.Embedding(sort_vocab_size, emb_dim )
        self.device = device
        if self._use_const_emb:
            self.treelstm = TreeLSTM(emb_dim*3, tree_dim)
        else:
            self.treelstm = TreeLSTM(emb_dim*2, tree_dim)

        self.next_to_last_size = 0
        if self._use_c:
            self.next_to_last_size = tree_dim * 3
        else:
            self.next_to_last_size = tree_dim * 2

        if self._use_dot_product:
            self.next_to_last_size+=1


        self.fc1 = nn.Linear(self.next_to_last_size, tree_dim)
        self.fc2 = nn.Linear(tree_dim, out_dim)


    def metadata(self):
        return {"emb_dim": self._emb_dim,
                "tree_dim": self._tree_dim,
                "use_c": self._use_c,
                "use_const_emb": self._use_const_emb,
                "use_dot_product": self._use_dot_product,
                "model": "old_model"
        }

    def forward(self, cube, lit_a, lit_b):
        h_a_raw, c_a_raw, a_sz = self.forward_a_tree(lit_a)
        h_b_raw, c_b_raw, b_sz = self.forward_a_tree(lit_b)

        h_a = TLUtil.stack_last_h(h_a_raw, a_sz)
        h_b = TLUtil.stack_last_h(h_b_raw, b_sz)

        assert(h_a.shape[0] == h_b.shape[0])
        # assert(h_a.shape[0] == h_c.shape[0])
        batch_size = h_a.shape[0]

        #compute the dot product here
        if self._use_dot_product:
            dotp = torch.diag(torch.matmul(h_a, torch.t(h_b)))
            dotp = dotp.view(batch_size, 1, -1)
            # print("dotp shape", dotp.shape)

        h_a = h_a.view(batch_size, 1, -1)
        h_b = h_b.view(batch_size, 1, -1)
        # print(h_a.shape, h_b.shape, h_c.shape)
        # fuse_a_b = torch.matmul(h_a, h_b)
        # print(fuse_a_b.shape)

        if self._use_c:
            h_c_raw, c_c_raw, c_sz = self.forward_a_tree(cube)
            # print(h_a.shape, h_b.shape, h_c.shape)
            h_c = TLUtil.stack_last_h(h_c_raw, c_sz)
            h_c = h_c.view(batch_size, 1, -1)
            h = torch.cat((h_c, h_a, h_b), dim = -1)
        else:
            h = torch.cat((h_a, h_b), dim = -1)

        # print(h.shape)
        if self._use_dot_product:
            h = torch.cat((h, dotp), dim = -1)
        # h = torch.matmul(h_c, fuse_a_b)
        # print(h.shape)
        logits = self.fc2(F.relu(self.fc1(h)))
        if self.training:
            return logits.view(batch_size, -1)
        else:
            return logits.view(batch_size, -1), {
                "h_a_raw": h_a_raw,
                "h_b_raw": h_b_raw,
            }

    def forward_a_tree(self, tree):
        features = tree["features"].to(self.device)
        node_order = tree["node_order"].to(self.device)
        adjacency_list = tree["adjacency_list"].to(self.device)
        edge_order = tree["edge_order"].to(self.device)
        # print(features.shape)
        token_feat = features[:,0]
        sort_feat = features[:,1]
        token_emb = self.emb(token_feat)
        sort_emb = self.sort_emb(sort_feat)
        # print(token_emb.shape)
        # print(const_emb.shape)
        if self._use_const_emb:
            const_emb = features[:, 2:2+self._emb_dim]*1.0
            features = torch.cat((token_emb, sort_emb, const_emb), dim = 1)
        else:
            features = torch.cat((token_emb, sort_emb), dim = 1)
        # features = token_emb
        h, c = self.treelstm(features, node_order, adjacency_list, edge_order)
        return h,c, tree["tree_sizes"] 
