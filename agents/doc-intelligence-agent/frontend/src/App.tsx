import React, { useState, useEffect } from 'react';
import { DocumentExplorer } from './components/DocumentExplorer';
import { ChatInterface } from './components/ChatInterface';
import { CitationDrawer } from './components/CitationDrawer';
import { Message, Citation, DocumentMetadata } from './types';
import { askAgent, fetchIndexedDocuments, sendFeedback } from './api/client';

export const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isDocsLoading, setIsDocsLoading] = useState(false);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);

  const loadDocuments = async () => {
    setIsDocsLoading(true);
    try {
      const docs = await fetchIndexedDocuments();
      setDocuments(docs);
    } finally {
      setIsDocsLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  const handleSendMessage = async (text: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await askAgent(text);
      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        text: response.answer,
        timestamp: new Date().toLocaleTimeString(),
        citations: response.citations,
        raw_chunks: response.raw_chunks,
      };
      setMessages((prev) => [...prev, agentMessage]);
    } catch (err: any) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'agent',
        text: `Error processing query: ${err.message || 'Unknown network error'}. Please ensure Vertex AI RAG corpus is configured and documents are indexed.`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 font-sans">
      <DocumentExplorer
        documents={documents}
        onRefresh={loadDocuments}
        isLoading={isDocsLoading}
      />

      <ChatInterface
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        onSelectCitation={(cite) => setSelectedCitation(cite)}
        onSendFeedback={(score, query) => sendFeedback(score, undefined, query)}
      />

      <CitationDrawer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
};

export default App;

